/**
 * Servidor HTTP local da interface web + API da carteira.
 *
 * Usa apenas o módulo http do Node — não há framework. As operações que
 * envolvem IA ou Telegram são delegadas ao script Python por injeção
 * (`servicos`), o que também permite testá-las sem rede.
 */

import fs from "node:fs";
import http from "node:http";
import path from "node:path";

import { ConfiguracaoIaError } from "../config/configIa.js";
import * as envPainel from "../config/envPainel.js";
import { WEB_DIR } from "../config/paths.js";
import * as authService from "../core/authService.js";
import * as portfolio from "../core/portfolio.js";
import * as storage from "../core/storage.js";
import { AutenticacaoError, conferirCredenciais, configuracaoAuth } from "../core/usuarios.js";
import { VERSAO } from "../../version.js";
import * as ambiente from "./ambiente.js";
import * as analiseExterna from "./analiseExterna.js";
import { cookieLogout, cookieSessao, tokenDaRequisicao } from "./cookies.js";
import * as limitadorLogin from "./limitadorLogin.js";

const TIPOS_MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

const SERVICOS_PADRAO = {
  executarAnalise: analiseExterna.executarAnalise,
  enviarUltimaAoTelegram: analiseExterna.enviarUltimaAoTelegram,
  previaTelegram: analiseExterna.previaTelegram,
  testarTelegram: analiseExterna.testarTelegram,
  testarIa: analiseExterna.testarIa,
  statusIa: ambiente.statusIa,
  telegramConfigurado: ambiente.telegramConfigurado,
  modeloIa: ambiente.modeloIa,
  provedorIa: ambiente.provedorIa,
  lerAmbiente: envPainel.lerPainelEnv,
  salvarAmbiente: envPainel.salvarPainelEnv,
};

function responderJson(res, dados, status = 200) {
  const corpo = Buffer.from(JSON.stringify(dados), "utf8");
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": corpo.length,
    "Cache-Control": "no-store",
  });
  res.end(corpo);
}

const responderErro = (res, mensagem, status = 400) =>
  responderJson(res, { erro: mensagem }, status);

function lerCorpo(req, limiteBytes = 1_000_000) {
  return new Promise((resolve, reject) => {
    const pedacos = [];
    let tamanho = 0;
    req.on("data", (pedaco) => {
      tamanho += pedaco.length;
      if (tamanho > limiteBytes) {
        reject(new Error("Corpo da requisição excede o limite permitido."));
        req.destroy();
        return;
      }
      pedacos.push(pedaco);
    });
    req.on("error", reject);
    req.on("end", () => {
      const bruto = Buffer.concat(pedacos).toString("utf8").trim();
      if (!bruto) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(bruto));
      } catch {
        reject(new Error("Corpo da requisição não é JSON válido."));
      }
    });
  });
}

/** Serve um arquivo de web/, bloqueando qualquer tentativa de sair do diretório. */
function servirArquivo(res, nome) {
  const raiz = path.resolve(WEB_DIR);
  const alvo = path.resolve(raiz, nome);

  if (alvo !== raiz && !alvo.startsWith(raiz + path.sep)) {
    responderErro(res, "Arquivo não encontrado.", 404);
    return;
  }
  if (!fs.existsSync(alvo) || !fs.statSync(alvo).isFile()) {
    responderErro(res, "Arquivo não encontrado.", 404);
    return;
  }

  const dados = fs.readFileSync(alvo);
  const tipo = TIPOS_MIME[path.extname(alvo).toLowerCase()] || "application/octet-stream";
  res.writeHead(200, {
    "Content-Type": tipo.startsWith("text/") || tipo.endsWith("javascript") || tipo.endsWith("json")
      ? `${tipo}; charset=utf-8`
      : tipo,
    "Content-Length": dados.length,
    "Cache-Control": "no-store",
  });
  res.end(dados);
}

/** Segredo de sessão configurado, ou null se ainda não houver usuário cadastrado. */
function segredoSessaoOuNulo() {
  try {
    return configuracaoAuth().segredo_sessao;
  } catch (erro) {
    if (erro instanceof AutenticacaoError) return null;
    throw erro;
  }
}

/** true se a requisição carrega um cookie de sessão válido. */
function sessaoValida(req) {
  const segredo = segredoSessaoOuNulo();
  return Boolean(segredo) && authService.tokenValido(tokenDaRequisicao(req), segredo);
}

/** POST /api/auth/login — única rota que confere usuário e senha. */
async function tratarLogin(req, res) {
  const ip = req.socket.remoteAddress || "desconhecido";
  if (limitadorLogin.bloqueado(ip)) {
    responderErro(res, "Muitas tentativas de login. Aguarde alguns minutos.", 429);
    return;
  }

  const corpo = await lerCorpo(req);

  let config;
  try {
    config = configuracaoAuth();
  } catch (erro) {
    if (!(erro instanceof AutenticacaoError)) throw erro;
    // O detalhe (caminho do arquivo) fica só no terminal do servidor —
    // devolver isso na resposta HTTP exporia estrutura de diretório e nome
    // de usuário do sistema operacional a quem só está tentando entrar.
    process.stderr.write(`\n  ${erro.message}\n\n`);
    responderErro(res, 'Login ainda não configurado. Peça para rodar "node scripts/criarLogin.js".', 500);
    return;
  }

  const usuarioAutenticado = conferirCredenciais(config.usuarios, corpo.usuario, corpo.senha);

  if (!usuarioAutenticado) {
    limitadorLogin.registrarFalha(ip);
    responderErro(res, "Usuário ou senha inválidos.", 401);
    return;
  }

  limitadorLogin.limpar(ip);
  const token = authService.criarToken(config.segredo_sessao);
  res.setHeader("Set-Cookie", cookieSessao(token, authService.SESSAO_MS));
  responderJson(res, { ok: true, usuario: usuarioAutenticado });
}

/**
 * Cria o servidor HTTP.
 *
 * @param {object} servicos Sobrescreve as operações externas (IA, Telegram).
 */
export function criarServidor(servicos = {}) {
  const svc = { ...SERVICOS_PADRAO, ...servicos };

  // Uma análise por vez: a chamada à IA é cara e demorada.
  let analiseEmAndamento = false;

  const servidor = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    const rota = url.pathname;

    try {
      // ── Login (público — só quem já entrou passa daqui pra frente) ──
      if (req.method === "GET" && rota === "/login") {
        servirArquivo(res, "login.html");
        return;
      }
      if (req.method === "POST" && rota === "/api/auth/login") {
        await tratarLogin(req, res);
        return;
      }
      if (req.method === "POST" && rota === "/api/auth/logout") {
        res.setHeader("Set-Cookie", cookieLogout());
        responderJson(res, { ok: true });
        return;
      }
      // Só o número da versão — a tela de login precisa exibi-la antes de
      // qualquer sessão existir. Sem dado nenhum da carteira.
      if (req.method === "GET" && rota === "/api/versao") {
        responderJson(res, { versao: VERSAO });
        return;
      }

      // ── Arquivos estáticos: só código, sem dado da carteira — sempre públicos ──
      if (req.method === "GET" && rota.startsWith("/static/")) {
        servirArquivo(res, decodeURIComponent(rota.slice("/static/".length)));
        return;
      }

      const autenticado = sessaoValida(req);

      if (req.method === "GET" && (rota === "/" || rota === "/index.html")) {
        if (!autenticado) {
          res.writeHead(302, { Location: "/login" });
          res.end();
          return;
        }
        servirArquivo(res, "index.html");
        return;
      }

      // ── Dali em diante, toda rota /api/* exige sessão válida ──
      if (rota.startsWith("/api/") && !autenticado) {
        responderErro(res, "Autenticação necessária.", 401);
        return;
      }

      // ── GET ──
      if (req.method === "GET") {
        if (rota === "/api/carteira") {
          responderJson(res, portfolio.load());
          return;
        }
        if (rota === "/api/analise") {
          responderJson(res, storage.ultimaAnalise() || { vazio: true });
          return;
        }
        if (rota === "/api/historico") {
          const limite = Number.parseInt(url.searchParams.get("limite") ?? "60", 10);
          const quantas = Number.isFinite(limite) ? limite : 60;
          responderJson(res, {
            serie: storage.historico(quantas),
            execucoes: storage.execucoes(quantas),
          });
          return;
        }
        if (rota === "/api/status") {
          const { ok, motivo } = svc.statusIa();
          responderJson(res, {
            ia_disponivel: ok,
            ia_motivo: motivo,
            telegram_configurado: svc.telegramConfigurado(),
            modelo: svc.modeloIa(),
            provedor: svc.provedorIa(),
            versao: VERSAO,
          });
          return;
        }
        if (rota === "/api/ambiente") {
          responderJson(res, svc.lerAmbiente());
          return;
        }
        responderErro(res, "Rota não encontrada.", 404);
        return;
      }

      // ── POST / PUT / DELETE ──
      if (req.method === "POST") {
        if (rota === "/api/analise") {
          const usarIa = url.searchParams.get("ia") !== "0";
          if (analiseEmAndamento) {
            responderErro(res, "Já existe uma análise em andamento.", 409);
            return;
          }
          analiseEmAndamento = true;
          try {
            responderJson(res, await svc.executarAnalise({ usarIa }));
          } finally {
            analiseEmAndamento = false;
          }
          return;
        }

        const corpo = await lerCorpo(req);

        if (rota === "/api/posicoes") {
          responderJson(res, portfolio.adicionar(corpo), 201);
          return;
        }
        if (rota === "/api/config") {
          responderJson(res, portfolio.atualizarConfig(corpo));
          return;
        }
        if (rota === "/api/ambiente") {
          responderJson(res, svc.salvarAmbiente(corpo));
          return;
        }
        if (rota === "/api/telegram") {
          const completo = url.searchParams.get("completo") === "1";
          responderJson(res, {
            ok: true,
            ...(await svc.enviarUltimaAoTelegram({ completo })),
          });
          return;
        }
        if (rota === "/api/telegram/previa") {
          const completo = url.searchParams.get("completo") === "1";
          responderJson(res, await svc.previaTelegram({ completo }));
          return;
        }
        if (rota === "/api/telegram/testar") {
          responderJson(res, await svc.testarTelegram());
          return;
        }
        if (rota === "/api/ia/testar") {
          responderJson(res, await svc.testarIa(corpo.provedor));
          return;
        }
        responderErro(res, "Rota não encontrada.", 404);
        return;
      }

      if (req.method === "PUT" && rota.startsWith("/api/posicoes/")) {
        const corpo = await lerCorpo(req);
        const posId = rota.slice("/api/posicoes/".length);
        responderJson(res, portfolio.atualizar(posId, corpo));
        return;
      }

      if (req.method === "DELETE" && rota.startsWith("/api/posicoes/")) {
        portfolio.remover(rota.slice("/api/posicoes/".length));
        responderJson(res, { ok: true });
        return;
      }

      responderErro(res, "Rota não encontrada.", 404);
    } catch (erro) {
      if (erro instanceof portfolio.ValidacaoError) {
        const naoEncontrada = erro.message.includes("nao encontrada");
        responderErro(res, erro.message, naoEncontrada ? 404 : 422);
        return;
      }
      if (erro instanceof ConfiguracaoIaError) {
        responderErro(res, erro.message, 422);
        return;
      }
      if (erro instanceof AutenticacaoError) {
        // Mesmo cuidado de tratarLogin: o detalhe vai só para o terminal.
        process.stderr.write(`\n  ${erro.message}\n\n`);
        responderErro(res, 'Login ainda não configurado. Peça para rodar "node scripts/criarLogin.js".', 500);
        return;
      }
      if (erro.message.includes("JSON válido") || erro.message.includes("limite permitido")) {
        responderErro(res, erro.message, 400);
        return;
      }
      responderErro(res, `Erro interno: ${erro.message}`, 500);
    }
  });

  return servidor;
}
