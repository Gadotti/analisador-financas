import fs from "node:fs";

import { ConfiguracaoIaError } from "../src/config/configIa.js";
import {
  execucoesFile,
  lastAnalysisFile,
  portfolioFile,
  usuariosFile,
} from "../src/config/paths.js";
import * as portfolio from "../src/core/portfolio.js";
import { criarServidor } from "../src/server/app.js";
import * as limitadorLogin from "../src/server/limitadorLogin.js";
import { VERSAO } from "../version.js";
import {
  dataDirTemporario,
  gravarAnalise,
  snapshotExemplo,
  usuarioAuthExemplo,
} from "./helpers/ambiente.js";

let ambiente;
let credenciais;
let cookieSessao;
let servidor;
let base;
let servicos;

/**
 * Serviços falsos: nenhum teste toca a rede nem dispara o script Python.
 * O estado fica num objeto próprio para poder ser ajustado por teste, mesmo
 * depois de o servidor ter copiado as funções.
 */
function ambientePainelExemplo() {
  return {
    ia_provedor: "anthropic",
    provedores: {
      anthropic: {
        origem_chave: "arquivo",
        variavel_chave: "",
        model: "claude-opus-5",
        effort: "medium",
        base_url: "",
        fallback: "",
        busca_web: "",
        max_tokens: "",
        api_key_definida: true,
      },
      kimi: {
        origem_chave: "",
        variavel_chave: "",
        model: "",
        effort: "",
        base_url: "",
        fallback: "",
        busca_web: "",
        max_tokens: "",
        api_key_definida: false,
      },
    },
    telegram: { chat_id: "42", bot_token_definido: true },
    brapi_token_definido: false,
  };
}

function servicosFalsos() {
  const estado = {
    chamadas: [],
    erroAnalise: null,
    respostaAnalise: null,
    ambiente: ambientePainelExemplo(),
    erroSalvarAmbiente: null,
    erroTestarIa: null,
  };

  return {
    estado,
    executarAnalise(opcoes) {
      estado.chamadas.push(["analise", opcoes]);
      if (estado.erroAnalise) return Promise.reject(estado.erroAnalise);
      if (estado.respostaAnalise) return estado.respostaAnalise(opcoes);
      return Promise.resolve({ snapshot: snapshotExemplo(), ia: null, fundamentos: null });
    },
    enviarUltimaAoTelegram(opcoes) {
      estado.chamadas.push(["telegram", opcoes]);
      return Promise.resolve({ ok: true });
    },
    previaTelegram(opcoes) {
      estado.chamadas.push(["telegram-previa", opcoes]);
      return Promise.resolve({ ok: true, texto: "📊 R$ 1,00", modo: "resumo" });
    },
    testarTelegram() {
      estado.chamadas.push(["telegram-testar"]);
      return Promise.resolve({ ok: true, bot: "Carteira Bot" });
    },
    testarIa(provedor) {
      estado.chamadas.push(["ia-testar", provedor]);
      if (estado.erroTestarIa) return Promise.reject(estado.erroTestarIa);
      return Promise.resolve({ ok: true, provedor: provedor || "anthropic", modelo: "claude-opus-5" });
    },
    statusIa: () => ({ ok: true, motivo: "" }),
    telegramConfigurado: () => true,
    modeloIa: () => "claude-opus-5",
    provedorIa: () => "anthropic",
    lerAmbiente: () => estado.ambiente,
    salvarAmbiente(corpo) {
      estado.chamadas.push(["salvar-ambiente", corpo]);
      if (estado.erroSalvarAmbiente) throw estado.erroSalvarAmbiente;
      return estado.ambiente;
    },
    verificarAtualizacao() {
      estado.chamadas.push(["verificar-atualizacao"]);
      return Promise.resolve(
        estado.atualizacao || {
          versao_atual: VERSAO,
          versao_disponivel: VERSAO,
          disponivel: false,
          url: null,
          publicado_em: null,
          erro: null,
        }
      );
    },
  };
}

/** Requisição sem cookie de sessão — para os testes de acesso anônimo. */
async function pedirSemAuth(caminho, opcoes = {}) {
  const resposta = await fetch(`${base}${caminho}`, {
    ...opcoes,
    redirect: "manual",
    headers: {
      ...(opcoes.body ? { "Content-Type": "application/json" } : {}),
      ...(opcoes.headers || {}),
    },
  });
  const texto = await resposta.text();
  let corpo = texto;
  try {
    corpo = JSON.parse(texto);
  } catch {
    // conteúdo estático
  }
  return { status: resposta.status, corpo, tipo: resposta.headers.get("content-type"), resposta };
}

/** Toda a suíte roda autenticada por padrão — é o comportamento normal do app. */
async function pedir(caminho, opcoes = {}) {
  return pedirSemAuth(caminho, {
    ...opcoes,
    headers: { Cookie: cookieSessao, ...(opcoes.headers || {}) },
  });
}

async function fazerLogin(usuario, senha) {
  const resposta = await fetch(`${base}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, senha }),
  });
  const corpo = await resposta.json();
  const setCookie = resposta.headers.get("set-cookie");
  return { status: resposta.status, corpo, cookie: setCookie ? setCookie.split(";")[0] : null };
}

beforeAll(async () => {
  ambiente = dataDirTemporario();
  credenciais = usuarioAuthExemplo(ambiente.dir);

  servicos = servicosFalsos();
  servidor = criarServidor(servicos);
  await new Promise((resolve) => servidor.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${servidor.address().port}`;

  const login = await fazerLogin(credenciais.usuario, credenciais.senha);
  cookieSessao = login.cookie;
});

afterAll(async () => {
  await new Promise((resolve) => servidor.close(resolve));
  ambiente.limpar();
});

beforeEach(() => {
  fs.rmSync(portfolioFile(), { force: true });
  fs.rmSync(lastAnalysisFile(), { force: true });
  fs.rmSync(execucoesFile(), { force: true });
  servicos.estado.chamadas.length = 0;
  servicos.estado.erroAnalise = null;
  servicos.estado.respostaAnalise = null;
  servicos.estado.ambiente = ambientePainelExemplo();
  servicos.estado.erroSalvarAmbiente = null;
  servicos.estado.erroTestarIa = null;
  servicos.estado.atualizacao = null;
  limitadorLogin.reiniciar();
});

describe("arquivos estáticos", () => {
  test("serve a interface na raiz", async () => {
    const { status, corpo, tipo } = await pedir("/");
    expect(status).toBe(200);
    expect(tipo).toMatch(/text\/html/);
    expect(corpo).toMatch(/<title>Analisador de carteira<\/title>/);
  });

  test.each([
    ["/static/style.css", /text\/css/],
    ["/static/app.js", /javascript/],
    ["/static/js/alocacao.js", /javascript/],
  ])("serve %s", async (caminho, tipoEsperado) => {
    const { status, tipo } = await pedir(caminho);
    expect(status).toBe(200);
    expect(tipo).toMatch(tipoEsperado);
  });

  test.each([
    ["/static/../package.json"],
    ["/static/%2e%2e/package.json"],
    ["/static/nao-existe.css"],
    ["/static/"],
  ])("responde 404 para %s", async (caminho) => {
    expect((await pedir(caminho)).status).toBe(404);
  });
});

describe("autenticação", () => {
  test("GET / sem sessão redireciona para /login", async () => {
    const { status, resposta } = await pedirSemAuth("/");
    expect(status).toBe(302);
    expect(resposta.headers.get("location")).toBe("/login");
  });

  test("GET /login é público e serve a tela de login", async () => {
    const { status, tipo, corpo } = await pedirSemAuth("/login");
    expect(status).toBe(200);
    expect(tipo).toMatch(/text\/html/);
    expect(corpo).toMatch(/form-login/);
  });

  test("GET /api/versao é público — a tela de login mostra a versão sem sessão", async () => {
    const { status, corpo } = await pedirSemAuth("/api/versao");
    expect(status).toBe(200);
    expect(corpo).toEqual({ versao: VERSAO });
  });

  test.each([
    ["/api/carteira"],
    ["/api/analise"],
    ["/api/historico"],
    ["/api/status"],
    ["/api/ambiente"],
    ["/api/atualizacao"],
    ["/api/backup"],
  ])("GET %s sem sessão responde 401", async (caminho) => {
    const { status, corpo } = await pedirSemAuth(caminho);
    expect(status).toBe(401);
    expect(corpo.erro).toMatch(/Autenticação necessária/);
  });

  test("POST /api/config sem sessão responde 401 e não grava nada", async () => {
    const { status } = await pedirSemAuth("/api/config", {
      method: "POST",
      body: JSON.stringify({ perfil: "Invasor" }),
    });
    expect(status).toBe(401);
  });

  test("DELETE /api/posicoes/x sem sessão responde 401", async () => {
    expect((await pedirSemAuth("/api/posicoes/x", { method: "DELETE" })).status).toBe(401);
  });

  test("POST /api/auth/login com senha errada responde 401 e não grava cookie", async () => {
    const login = await fazerLogin(credenciais.usuario, "senha-errada");
    expect(login.status).toBe(401);
    expect(login.cookie).toBeNull();
  });

  test("POST /api/auth/login com usuário errado responde 401", async () => {
    const login = await fazerLogin("outro-usuario", credenciais.senha);
    expect(login.status).toBe(401);
  });

  test("POST /api/auth/login com credenciais corretas grava um cookie HttpOnly", async () => {
    const login = await fazerLogin(credenciais.usuario, credenciais.senha);
    expect(login.status).toBe(200);
    expect(login.corpo).toEqual({ ok: true, usuario: credenciais.usuario });
    expect(login.cookie).toMatch(/^sessao=/);
  });

  test("o cookie emitido autentica as chamadas seguintes", async () => {
    const login = await fazerLogin(credenciais.usuario, credenciais.senha);
    const { status } = await pedirSemAuth("/api/carteira", { headers: { Cookie: login.cookie } });
    expect(status).toBe(200);
  });

  test("bloqueia novas tentativas após MAX_TENTATIVAS falhas", async () => {
    for (let i = 0; i < limitadorLogin.MAX_TENTATIVAS; i += 1) {
      await fazerLogin(credenciais.usuario, "senha-errada");
    }
    const bloqueado = await fazerLogin(credenciais.usuario, credenciais.senha);
    expect(bloqueado.status).toBe(429);
  });

  test("POST /api/auth/logout limpa o cookie e a sessão deixa de valer", async () => {
    const login = await fazerLogin(credenciais.usuario, credenciais.senha);
    const logout = await fetch(`${base}/api/auth/logout`, {
      method: "POST",
      headers: { Cookie: login.cookie },
    });
    expect(logout.status).toBe(200);
    expect(await logout.json()).toEqual({ ok: true });
    expect(logout.headers.get("set-cookie")).toMatch(/Max-Age=0/);

    const depoisDoLogout = await pedirSemAuth("/api/carteira", { headers: { Cookie: login.cookie } });
    expect(depoisDoLogout.status).toBe(200); // o token em si continua válido...

    const semCookieNenhum = await pedirSemAuth("/api/carteira");
    expect(semCookieNenhum.status).toBe(401); // ...só o navegador não volta a enviá-lo.
  });

  test("um cookie de sessão adulterado é recusado", async () => {
    const login = await fazerLogin(credenciais.usuario, credenciais.senha);
    const adulterado = `${login.cookie}x`;
    const { status } = await pedirSemAuth("/api/carteira", { headers: { Cookie: adulterado } });
    expect(status).toBe(401);
  });

  test("POST /api/auth/login com o login ainda não configurado responde 500", async () => {
    const arquivoOriginal = fs.readFileSync(usuariosFile(), "utf8");
    fs.rmSync(usuariosFile());
    try {
      const login = await fazerLogin(credenciais.usuario, credenciais.senha);
      expect(login.status).toBe(500);
      expect(login.corpo.erro).toMatch(/criarLogin\.js/);
    } finally {
      fs.writeFileSync(usuariosFile(), arquivoOriginal, "utf8");
    }
  });
});

describe("GET /api", () => {
  test("devolve a carteira, criando-a se necessário", async () => {
    const { status, corpo } = await pedir("/api/carteira");
    expect(status).toBe(200);
    expect(corpo.posicoes).toEqual([]);
    expect(corpo.config.limite_fgc).toBe(250000);
  });

  test("sinaliza quando não há análise salva", async () => {
    expect((await pedir("/api/analise")).corpo).toEqual({ vazio: true });
  });

  test("devolve a última análise gravada pelo script", async () => {
    gravarAnalise(ambiente.dir, snapshotExemplo());
    expect((await pedir("/api/analise")).corpo.snapshot.data).toBe("2026-09-01");
  });

  test("devolve a série histórica respeitando o limite", async () => {
    gravarAnalise(ambiente.dir, snapshotExemplo());
    const { corpo } = await pedir("/api/historico?limite=5");
    expect(corpo.serie).toHaveLength(1);
    expect(corpo.serie[0].valor_atual).toBe(22000);
  });

  test("cai no padrão quando o limite não é numérico", async () => {
    expect((await pedir("/api/historico?limite=abc")).status).toBe(200);
  });

  test("devolve também o log de execuções gravado pelo script", async () => {
    fs.writeFileSync(
      execucoesFile(),
      JSON.stringify([{ gerado_em: "2026-09-07T08:31:19", status_ia: "erro", ia_erro: "HTTP 429" }]),
      "utf8"
    );
    const { corpo } = await pedir("/api/historico");
    expect(corpo.execucoes).toHaveLength(1);
    expect(corpo.execucoes[0].ia_erro).toBe("HTTP 429");
  });

  test("devolve log vazio quando nenhuma execução foi registrada", async () => {
    expect((await pedir("/api/historico")).corpo.execucoes).toEqual([]);
  });

  test("informa a disponibilidade de IA e Telegram", async () => {
    const { corpo } = await pedir("/api/status");
    expect(corpo).toEqual({
      ia_disponivel: true,
      ia_motivo: "",
      telegram_configurado: true,
      modelo: "claude-opus-5",
      provedor: "anthropic",
      versao: VERSAO,
    });
  });

  test("informa quando há uma versão nova publicada", async () => {
    servicos.estado.atualizacao = {
      versao_atual: VERSAO,
      versao_disponivel: "99.0.0",
      disponivel: true,
      url: "https://github.com/Gadotti/analisador-financas/releases/tag/v99.0.0",
      publicado_em: "2026-09-01T00:00:00Z",
      erro: null,
    };
    const { corpo } = await pedir("/api/atualizacao");
    expect(corpo).toEqual(servicos.estado.atualizacao);
  });

  test("responde 404 em rota desconhecida", async () => {
    const { status, corpo } = await pedir("/api/nao-existe");
    expect(status).toBe(404);
    expect(corpo.erro).toMatch(/não encontrada/);
  });

  test("devolve o painel de ambiente sem segredos", async () => {
    const { status, corpo } = await pedir("/api/ambiente");
    expect(status).toBe(200);
    expect(corpo).toEqual(servicos.estado.ambiente);
  });
});

describe("GET /api/backup", () => {
  test("baixa data/ compactada, sem o arquivo de login", async () => {
    fs.writeFileSync(portfolioFile(), '{"posicoes":[]}', "utf8");

    const resposta = await fetch(`${base}/api/backup`, { headers: { Cookie: cookieSessao } });
    expect(resposta.status).toBe(200);
    expect(resposta.headers.get("content-type")).toBe("application/zip");
    expect(resposta.headers.get("content-disposition")).toMatch(/^attachment; filename="backup-\d{4}-\d{2}-\d{2}\.zip"$/);

    const zip = Buffer.from(await resposta.arrayBuffer());
    expect(zip.readUInt32LE(0)).toBe(0x04034b50); // assinatura do primeiro cabeçalho local ZIP
    expect(zip.includes("usuarios.json")).toBe(false);
  });
});

describe("POST /api/ambiente", () => {
  test("grava as alterações e devolve o painel atualizado", async () => {
    const alteracoes = { provedores: { anthropic: { model: "claude-sonnet-5" } } };
    const { status, corpo } = await pedir("/api/ambiente", {
      method: "POST",
      body: JSON.stringify(alteracoes),
    });
    expect(status).toBe(200);
    expect(corpo).toEqual(servicos.estado.ambiente);
    expect(servicos.estado.chamadas).toEqual([["salvar-ambiente", alteracoes]]);
  });

  test("responde 422 quando o provedor informado é inválido", async () => {
    servicos.estado.erroSalvarAmbiente = new ConfiguracaoIaError("IA_PROVEDOR inválido: \"---\".");
    const { status, corpo } = await pedir("/api/ambiente", {
      method: "POST",
      body: JSON.stringify({ ia_provedor: "---" }),
    });
    expect(status).toBe(422);
    expect(corpo.erro).toMatch(/IA_PROVEDOR inválido/);
  });
});

describe("CRUD de posições", () => {
  const nova = { tipo: "fii", ticker: "MXRF11", quantidade: 100, preco_medio: 9.85 };

  test("cria uma posição e devolve 201", async () => {
    const { status, corpo } = await pedir("/api/posicoes", {
      method: "POST",
      body: JSON.stringify(nova),
    });
    expect(status).toBe(201);
    expect(corpo.ticker).toBe("MXRF11");
    expect(portfolio.load().posicoes).toHaveLength(1);
  });

  test("recusa dados inválidos com 422", async () => {
    const { status, corpo } = await pedir("/api/posicoes", {
      method: "POST",
      body: JSON.stringify({ tipo: "fii" }),
    });
    expect(status).toBe(422);
    expect(corpo.erro).toMatch(/'ticker' e obrigatorio/);
  });

  test("recusa corpo que não é JSON com 400", async () => {
    const resposta = await fetch(`${base}/api/posicoes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: cookieSessao },
      body: "isto não é json",
    });
    expect(resposta.status).toBe(400);
    expect((await resposta.json()).erro).toMatch(/não é JSON válido/);
  });

  test("atualiza uma posição existente", async () => {
    const criada = portfolio.adicionar(nova);
    const { status, corpo } = await pedir(`/api/posicoes/${criada.id}`, {
      method: "PUT",
      body: JSON.stringify({ ...nova, quantidade: 500 }),
    });
    expect(status).toBe(200);
    expect(corpo.quantidade).toBe(500);
  });

  test("remove uma posição", async () => {
    const criada = portfolio.adicionar(nova);
    const { status, corpo } = await pedir(`/api/posicoes/${criada.id}`, { method: "DELETE" });
    expect(status).toBe(200);
    expect(corpo).toEqual({ ok: true });
    expect(portfolio.load().posicoes).toHaveLength(0);
  });

  test("responde 404 ao atualizar posição inexistente", async () => {
    const { status } = await pedir("/api/posicoes/inexistente", {
      method: "PUT",
      body: JSON.stringify(nova),
    });
    expect(status).toBe(404);
  });

  test("responde 404 ao remover posição inexistente", async () => {
    expect((await pedir("/api/posicoes/xxx", { method: "DELETE" })).status).toBe(404);
  });

  test.each([["PUT"], ["DELETE"]])("responde 404 em %s fora de /api/posicoes", async (method) => {
    const body = method === "PUT" ? "{}" : undefined;
    expect((await pedir("/api/outra", { method, body })).status).toBe(404);
  });

  test("salva perfil e parâmetros de alerta", async () => {
    const { status, corpo } = await pedir("/api/config", {
      method: "POST",
      body: JSON.stringify({ perfil: "Renda mensal", config: { alerta_prejuizo_pct: 20 } }),
    });
    expect(status).toBe(200);
    expect(corpo.perfil).toBe("Renda mensal");
    expect(corpo.config.alerta_prejuizo_pct).toBe(20);
  });
});

describe("POST /api/analise", () => {
  test("delega ao script Python com IA por padrão", async () => {
    const { status, corpo } = await pedir("/api/analise", { method: "POST" });
    expect(status).toBe(200);
    expect(corpo.snapshot.data).toBe("2026-09-01");
    expect(servicos.estado.chamadas[0][0]).toBe("analise");
    expect(servicos.estado.chamadas[0][1]).toMatchObject({ usarIa: true });
    expect(servicos.estado.chamadas[0][1].aoRegistrar).toBeInstanceOf(Function);
  });

  test("pula a IA quando ia=0", async () => {
    await pedir("/api/analise?ia=0", { method: "POST" });
    expect(servicos.estado.chamadas[0][1]).toMatchObject({ usarIa: false });
  });

  test("converte falha do script em 500 com mensagem", async () => {
    servicos.estado.erroAnalise = new Error("A análise excedeu o tempo limite.");
    const { status, corpo } = await pedir("/api/analise", { method: "POST" });
    expect(status).toBe(500);
    expect(corpo.erro).toMatch(/tempo limite/);
  });

  test("recusa uma segunda análise simultânea com 409", async () => {
    let liberar;
    servicos.estado.respostaAnalise = () =>
      new Promise((resolve) => {
        liberar = () => resolve({ snapshot: snapshotExemplo() });
      });

    const primeira = pedir("/api/analise", { method: "POST" });
    await new Promise((r) => setTimeout(r, 30));
    const segunda = await pedir("/api/analise", { method: "POST" });

    expect(segunda.status).toBe(409);
    expect(segunda.corpo.erro).toMatch(/análise em andamento/);

    liberar();
    expect((await primeira).status).toBe(200);
  });
});

describe("GET /api/analise/status", () => {
  test("mostra em_andamento e a fase relatada pelo stderr do script durante a execução", async () => {
    let liberar;
    let aoRegistrar;
    servicos.estado.respostaAnalise = (opcoes) => {
      aoRegistrar = opcoes.aoRegistrar;
      return new Promise((resolve) => {
        liberar = () => resolve({ snapshot: snapshotExemplo() });
      });
    };

    const emAndamento = pedir("/api/analise", { method: "POST" });
    await new Promise((r) => setTimeout(r, 30));
    aoRegistrar("[1/3] Carregando carteira e cotações...");

    const { corpo } = await pedir("/api/analise/status");
    expect(corpo.em_andamento).toBe(true);
    expect(corpo.com_ia).toBe(true);
    expect(corpo.fase).toBe("[1/3] Carregando carteira e cotações...");
    expect(corpo.iniciada_em).not.toBeNull();

    liberar();
    await emAndamento;
  });

  test("guarda o erro de uma tentativa que quebrou, até a próxima começar", async () => {
    servicos.estado.erroAnalise = new Error("A análise excedeu o tempo limite.");
    await pedir("/api/analise", { method: "POST" });

    const { corpo } = await pedir("/api/analise/status");
    expect(corpo.em_andamento).toBe(false);
    expect(corpo.ultimo_erro).toMatch(/tempo limite/);
    expect(corpo.ultimo_erro_em).not.toBeNull();

    servicos.estado.erroAnalise = null;
    await pedir("/api/analise", { method: "POST" });
    const depois = await pedir("/api/analise/status");
    expect(depois.corpo.ultimo_erro).toBeNull();
  });
});

describe("POST /api/telegram", () => {
  test("dispara o reenvio da última análise na mensagem curta", async () => {
    const { status, corpo } = await pedir("/api/telegram", { method: "POST" });
    expect(status).toBe(200);
    expect(corpo).toEqual({ ok: true });
    expect(servicos.estado.chamadas[0]).toEqual(["telegram", { completo: false }]);
  });

  test("completo=1 pede o relatório inteiro", async () => {
    await pedir("/api/telegram?completo=1", { method: "POST" });
    expect(servicos.estado.chamadas[0]).toEqual(["telegram", { completo: true }]);
  });

  test("a prévia devolve o texto sem enviar nada", async () => {
    const { corpo } = await pedir("/api/telegram/previa", { method: "POST" });
    expect(corpo.texto).toContain("R$ 1,00");
    expect(servicos.estado.chamadas[0]).toEqual(["telegram-previa", { completo: false }]);
  });

  test("testa a conexão com o bot", async () => {
    expect((await pedir("/api/telegram/testar", { method: "POST" })).corpo.bot).toBe("Carteira Bot");
  });

  test("responde 404 em POST desconhecido", async () => {
    expect((await pedir("/api/nada", { method: "POST", body: "{}" })).status).toBe(404);
  });
});

describe("POST /api/ia/testar", () => {
  test("testa a conexão com o provedor ativo quando nenhum é informado", async () => {
    const { status, corpo } = await pedir("/api/ia/testar", { method: "POST", body: "{}" });
    expect(status).toBe(200);
    expect(corpo).toEqual({ ok: true, provedor: "anthropic", modelo: "claude-opus-5" });
    expect(servicos.estado.chamadas).toEqual([["ia-testar", undefined]]);
  });

  test("repassa o provedor escolhido na tela", async () => {
    const { corpo } = await pedir("/api/ia/testar", {
      method: "POST",
      body: JSON.stringify({ provedor: "kimi" }),
    });
    expect(corpo.provedor).toBe("kimi");
    expect(servicos.estado.chamadas).toEqual([["ia-testar", "kimi"]]);
  });

  test("propaga o erro de configuração ou de conexão", async () => {
    servicos.estado.erroTestarIa = new Error("ANTHROPIC_API_KEY não encontrada");
    const { status, corpo } = await pedir("/api/ia/testar", { method: "POST", body: "{}" });
    expect(status).toBe(500);
    expect(corpo.erro).toMatch(/ANTHROPIC_API_KEY/);
  });
});
