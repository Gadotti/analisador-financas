/**
 * web/js/historico.js — só o banner de andamento (`renderAndamentoAnalise`).
 *
 * Sem jsdom (mesmo critério dos demais testes de web/js/): um `document`
 * mínimo com o que a função usa (`classList`, `textContent`).
 */

function elemento() {
  const classes = new Set();
  return {
    textContent: "",
    classList: {
      add: (...cs) => cs.forEach((c) => classes.add(c)),
      remove: (...cs) => cs.forEach((c) => classes.delete(c)),
      contains: (c) => classes.has(c),
    },
  };
}

let renderAndamentoAnalise;
let tela;

beforeAll(async () => {
  ({ renderAndamentoAnalise } = await import("../../web/js/historico.js"));
});

beforeEach(() => {
  tela = {
    "#andamento-analise": elemento(),
    "#andamento-analise-texto": elemento(),
  };
  global.document = { querySelector: (seletor) => tela[seletor] };
});

afterEach(() => {
  delete global.document;
});

describe("renderAndamentoAnalise", () => {
  test("esconde o banner quando não há execução nem erro anterior", () => {
    tela["#andamento-analise"].classList.remove("hidden");
    renderAndamentoAnalise({
      em_andamento: false,
      com_ia: null,
      iniciada_em: null,
      fase: null,
      ultimo_erro: null,
      ultimo_erro_em: null,
    });
    expect(tela["#andamento-analise"].classList.contains("hidden")).toBe(true);
  });

  test("esconde o banner quando a consulta ao status falhou (status nulo)", () => {
    renderAndamentoAnalise(null);
    expect(tela["#andamento-analise"].classList.contains("hidden")).toBe(true);
  });

  test("mostra o tempo decorrido e a fase durante uma análise com IA", () => {
    const iniciada_em = new Date(Date.now() - 75_000).toISOString();
    renderAndamentoAnalise({
      em_andamento: true,
      com_ia: true,
      iniciada_em,
      fase: "[2/3] Consultando a IA — pode levar alguns minutos...",
      ultimo_erro: null,
      ultimo_erro_em: null,
    });

    expect(tela["#andamento-analise"].classList.contains("hidden")).toBe(false);
    expect(tela["#andamento-analise"].classList.contains("andamento-analise-erro")).toBe(false);
    expect(tela["#andamento-analise-texto"].textContent).toMatch(
      /^Analisando com IA há 1min 1[4-6]s — Consultando a IA — pode levar alguns minutos\.\.\.$/
    );
  });

  test("mostra 'Atualizando cotações' sem fase quando roda sem IA", () => {
    renderAndamentoAnalise({
      em_andamento: true,
      com_ia: false,
      iniciada_em: new Date().toISOString(),
      fase: null,
      ultimo_erro: null,
      ultimo_erro_em: null,
    });
    expect(tela["#andamento-analise-texto"].textContent).toMatch(/^Atualizando cotações há/);
  });

  test("mostra o erro da última tentativa quando não há execução em andamento", () => {
    renderAndamentoAnalise({
      em_andamento: false,
      com_ia: true,
      iniciada_em: null,
      fase: null,
      ultimo_erro: "A análise excedeu o tempo limite e foi interrompida.",
      ultimo_erro_em: "2026-09-01T12:00:00.000Z",
    });

    expect(tela["#andamento-analise"].classList.contains("hidden")).toBe(false);
    expect(tela["#andamento-analise"].classList.contains("andamento-analise-erro")).toBe(true);
    expect(tela["#andamento-analise-texto"].textContent).toMatch(
      /A análise excedeu o tempo limite e foi interrompida\.$/
    );
  });
});
