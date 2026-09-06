import fs from "node:fs";

import { ConfiguracaoIaError } from "../src/config/configIa.js";
import { lastAnalysisFile, portfolioFile } from "../src/config/paths.js";
import * as portfolio from "../src/core/portfolio.js";
import { criarServidor } from "../src/server/app.js";
import { VERSAO } from "../version.js";
import { dataDirTemporario, gravarAnalise, snapshotExemplo } from "./helpers/ambiente.js";

let ambiente;
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
  };

  return {
    estado,
    executarAnalise(opcoes) {
      estado.chamadas.push(["analise", opcoes]);
      if (estado.erroAnalise) return Promise.reject(estado.erroAnalise);
      if (estado.respostaAnalise) return estado.respostaAnalise();
      return Promise.resolve({ snapshot: snapshotExemplo(), ia: null, fundamentos: null });
    },
    enviarUltimaAoTelegram() {
      estado.chamadas.push(["telegram"]);
      return Promise.resolve({ ok: true });
    },
    testarTelegram() {
      estado.chamadas.push(["telegram-testar"]);
      return Promise.resolve({ ok: true, bot: "Carteira Bot" });
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
  };
}

async function pedir(caminho, opcoes = {}) {
  const resposta = await fetch(`${base}${caminho}`, {
    ...opcoes,
    headers: opcoes.body ? { "Content-Type": "application/json" } : undefined,
  });
  const texto = await resposta.text();
  let corpo = texto;
  try {
    corpo = JSON.parse(texto);
  } catch {
    // conteúdo estático
  }
  return { status: resposta.status, corpo, tipo: resposta.headers.get("content-type") };
}

beforeAll(async () => {
  ambiente = dataDirTemporario();
  servicos = servicosFalsos();
  servidor = criarServidor(servicos);
  await new Promise((resolve) => servidor.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${servidor.address().port}`;
});

afterAll(async () => {
  await new Promise((resolve) => servidor.close(resolve));
  ambiente.limpar();
});

beforeEach(() => {
  fs.rmSync(portfolioFile(), { force: true });
  fs.rmSync(lastAnalysisFile(), { force: true });
  servicos.estado.chamadas.length = 0;
  servicos.estado.erroAnalise = null;
  servicos.estado.respostaAnalise = null;
  servicos.estado.ambiente = ambientePainelExemplo();
  servicos.estado.erroSalvarAmbiente = null;
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
      headers: { "Content-Type": "application/json" },
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
    expect(servicos.estado.chamadas[0]).toEqual(["analise", { usarIa: true }]);
  });

  test("pula a IA quando ia=0", async () => {
    await pedir("/api/analise?ia=0", { method: "POST" });
    expect(servicos.estado.chamadas[0]).toEqual(["analise", { usarIa: false }]);
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

describe("POST /api/telegram", () => {
  test("dispara o reenvio da última análise", async () => {
    const { status, corpo } = await pedir("/api/telegram", { method: "POST" });
    expect(status).toBe(200);
    expect(corpo).toEqual({ ok: true });
    expect(servicos.estado.chamadas[0]).toEqual(["telegram"]);
  });

  test("testa a conexão com o bot", async () => {
    expect((await pedir("/api/telegram/testar", { method: "POST" })).corpo.bot).toBe("Carteira Bot");
  });

  test("responde 404 em POST desconhecido", async () => {
    expect((await pedir("/api/nada", { method: "POST", body: "{}" })).status).toBe(404);
  });
});
