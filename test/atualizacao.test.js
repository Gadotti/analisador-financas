import { consultarAtualizacao, reiniciar } from "../src/server/atualizacao.js";
import { VERSAO } from "../version.js";

const releaseRespondendo = (tagName, extra = {}) => async () => ({
  ok: true,
  json: async () => ({
    tag_name: tagName,
    html_url: `https://github.com/Gadotti/analisador-financas/releases/tag/${tagName}`,
    published_at: "2026-09-01T00:00:00Z",
    ...extra,
  }),
});

beforeEach(() => {
  reiniciar();
});

describe("consultarAtualizacao", () => {
  test("indica versão disponível quando a tag remota é maior", async () => {
    const partes = VERSAO.split(".").map(Number);
    const maior = [partes[0], partes[1], partes[2] + 1].join(".");
    const resultado = await consultarAtualizacao({ buscar: releaseRespondendo(`v${maior}`) });

    expect(resultado).toEqual({
      versao_atual: VERSAO,
      versao_disponivel: maior,
      disponivel: true,
      url: `https://github.com/Gadotti/analisador-financas/releases/tag/v${maior}`,
      publicado_em: "2026-09-01T00:00:00Z",
      erro: null,
    });
  });

  test("não indica atualização quando a tag remota é igual à instalada", async () => {
    const resultado = await consultarAtualizacao({ buscar: releaseRespondendo(`v${VERSAO}`) });
    expect(resultado.disponivel).toBe(false);
  });

  test("não indica atualização quando a tag remota é mais antiga", async () => {
    const partes = VERSAO.split(".").map(Number);
    const menor = [partes[0], partes[1], Math.max(partes[2] - 1, 0)].join(".");
    const resultado = await consultarAtualizacao({ buscar: releaseRespondendo(`v${menor}`) });
    expect(resultado.disponivel).toBe(false);
  });

  test("devolve disponivel:false com o erro quando o GitHub responde com falha, sem lançar", async () => {
    const buscar = async () => ({ ok: false, status: 503 });
    const resultado = await consultarAtualizacao({ buscar, forcar: true });

    expect(resultado.disponivel).toBe(false);
    expect(resultado.versao_atual).toBe(VERSAO);
    expect(resultado.erro).toMatch(/503/);
  });

  test("devolve disponivel:false com o erro quando a rede falha, sem lançar", async () => {
    const buscar = async () => {
      throw new Error("getaddrinfo ENOTFOUND api.github.com");
    };
    const resultado = await consultarAtualizacao({ buscar, forcar: true });

    expect(resultado.disponivel).toBe(false);
    expect(resultado.erro).toMatch(/ENOTFOUND/);
  });

  test("dentro da validade, não consulta a rede de novo", async () => {
    let chamadas = 0;
    const buscar = async () => {
      chamadas += 1;
      return releaseRespondendo("v99.0.0")();
    };
    const agora = Date.now();

    await consultarAtualizacao({ buscar, agora });
    await consultarAtualizacao({ buscar, agora: agora + 1000 });

    expect(chamadas).toBe(1);
  });

  test("forcar ignora o cache mesmo dentro da validade", async () => {
    let chamadas = 0;
    const buscar = async () => {
      chamadas += 1;
      return releaseRespondendo("v99.0.0")();
    };

    await consultarAtualizacao({ buscar });
    await consultarAtualizacao({ buscar, forcar: true });

    expect(chamadas).toBe(2);
  });

  test("consulta a rede de novo depois do cache expirar", async () => {
    let chamadas = 0;
    const buscar = async () => {
      chamadas += 1;
      return releaseRespondendo("v99.0.0")();
    };
    const agora = Date.now();

    await consultarAtualizacao({ buscar, agora });
    await consultarAtualizacao({ buscar, agora: agora + 7 * 60 * 60 * 1000 });

    expect(chamadas).toBe(2);
  });
});
