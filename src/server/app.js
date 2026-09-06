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
import * as portfolio from "../core/portfolio.js";
import * as storage from "../core/storage.js";
import * as ambiente from "./ambiente.js";
import * as analiseExterna from "./analiseExterna.js";

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
  testarTelegram: analiseExterna.testarTelegram,
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
      // ── Arquivos estáticos ──
      if (req.method === "GET" && (rota === "/" || rota === "/index.html")) {
        servirArquivo(res, "index.html");
        return;
      }
      if (req.method === "GET" && rota.startsWith("/static/")) {
        servirArquivo(res, decodeURIComponent(rota.slice("/static/".length)));
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
          responderJson(res, {
            serie: storage.historico(Number.isFinite(limite) ? limite : 60),
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
          await svc.enviarUltimaAoTelegram();
          responderJson(res, { ok: true });
          return;
        }
        if (rota === "/api/telegram/testar") {
          responderJson(res, await svc.testarTelegram());
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
      if (erro.message.includes("JSON válido") || erro.message.includes("limite permitido")) {
        responderErro(res, erro.message, 400);
        return;
      }
      responderErro(res, `Erro interno: ${erro.message}`, 500);
    }
  });

  return servidor;
}
