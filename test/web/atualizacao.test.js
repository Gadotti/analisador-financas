/**
 * web/js/atualizacao.js — a barra de aviso de nova versão.
 *
 * Sem jsdom (mesmo critério dos demais testes de web/js/): um `document`
 * mínimo com o que o módulo usa (`classList`, `textContent`, `href`).
 */

function elemento() {
  const classes = new Set();
  return {
    textContent: "",
    href: "",
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    },
  };
}

let renderAtualizacao;
let tela;

beforeAll(async () => {
  ({ renderAtualizacao } = await import("../../web/js/atualizacao.js"));
});

beforeEach(() => {
  tela = {
    "#banner-versao": elemento(),
    "#banner-versao-texto": elemento(),
    "#banner-versao-link": elemento(),
  };
  global.document = { querySelector: (seletor) => tela[seletor] };
});

afterEach(() => {
  delete global.document;
});

describe("renderAtualizacao", () => {
  test("esconde a barra quando não há atualização disponível", () => {
    tela["#banner-versao"].classList.remove("hidden"); // simula uma exibição anterior
    renderAtualizacao({ disponivel: false });
    expect(tela["#banner-versao"].classList.contains("hidden")).toBe(true);
  });

  test("esconde a barra quando a checagem falhou (dados vazios)", () => {
    renderAtualizacao(null);
    expect(tela["#banner-versao"].classList.contains("hidden")).toBe(true);
  });

  test("mostra a versão nova e o link da release quando há atualização", () => {
    renderAtualizacao({
      disponivel: true,
      versao_atual: "0.3.0",
      versao_disponivel: "0.4.0",
      url: "https://github.com/Gadotti/analisador-financas/releases/tag/v0.4.0",
    });

    expect(tela["#banner-versao"].classList.contains("hidden")).toBe(false);
    expect(tela["#banner-versao-texto"].textContent).toBe(
      "Nova versão disponível: 0.4.0 (você está na 0.3.0)."
    );
    expect(tela["#banner-versao-link"].href).toBe(
      "https://github.com/Gadotti/analisador-financas/releases/tag/v0.4.0"
    );
  });

  test("usa # como destino do link quando a release não trouxe url", () => {
    renderAtualizacao({ disponivel: true, versao_atual: "0.3.0", versao_disponivel: "0.4.0", url: null });
    expect(tela["#banner-versao-link"].href).toBe("#");
  });
});
