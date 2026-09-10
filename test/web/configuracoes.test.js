/**
 * web/js/configuracoes.js — o bloco "Mensagem do Telegram" da tela.
 *
 * Sem framework de DOM (não há jsdom no projeto): um `document` mínimo que
 * inventa um elemento para cada seletor pedido é suficiente, porque o módulo
 * só lê `.value`/`.checked` e, nos dias da semana, percorre `querySelectorAll`.
 *
 * O que estes testes travam é o contrato entre as duas metades: a tela declara
 * os blocos numa tabela e o `atualizarConfig` os valida noutra. Se uma tabela
 * ganhar um campo que a outra não conhece, o valor seria descartado em
 * silêncio — e o usuário veria o limiar voltar ao padrão depois de salvar.
 */

import fs from "node:fs";

import { dataDirTemporario } from "../helpers/ambiente.js";

/** Um input/select qualquer da tela, com o mínimo de DOM que o módulo usa. */
function elemento(valor = "") {
  const el = { value: valor, checked: false, innerHTML: "", textContent: "" };
  el.filhos = [];
  el.ouvintes = {};
  el.querySelectorAll = () => el.filhos;
  el.addEventListener = (evento, fn) => {
    el.ouvintes[evento] = fn;
  };
  return el;
}

/** Contêiner de dias da semana: sete caixas, como `montarTelegram` desenha. */
function containerDeDias(marcados = []) {
  const el = elemento();
  el.filhos = [0, 1, 2, 3, 4, 5, 6].map((i) => ({
    value: String(i),
    checked: marcados.includes(i),
  }));
  return el;
}

let tela;
let configuracoes;
let portfolio;
let temporario;

beforeAll(async () => {
  // Qualquer seletor pedido passa a existir, guardado para inspeção depois.
  tela = { "#tg-resumo-ia-dias-semana": containerDeDias([4]) };
  global.document = {
    querySelector(seletor) {
      tela[seletor] = tela[seletor] ?? elemento();
      return tela[seletor];
    },
  };
  configuracoes = await import("../../web/js/configuracoes.js");
  portfolio = await import("../../src/core/portfolio.js");
});

afterAll(() => {
  delete global.document;
});

beforeEach(() => {
  temporario = dataDirTemporario();
});

afterEach(() => {
  temporario.limpar();
});

describe("montarTelegram", () => {
  test("desenha um interruptor e os campos de cada bloco declarado", () => {
    configuracoes.montarTelegram();
    const html = tela["#tg-blocos"].innerHTML;

    expect(html).toContain('id="tg-movimento-ativo"');
    expect(html).toContain('id="tg-movimento-limiar-pct"');
    expect(html).toContain('id="tg-calendario-rf-marcos-dias"');
    expect(html).toContain('id="tg-semanal-dia-semana"');
  });

  test("a severidade é um select fechado, e não um campo livre", () => {
    configuracoes.montarTelegram();
    const html = tela["#tg-blocos"].innerHTML;

    expect(html).toContain('<select id="tg-alertas-severidade-minima">');
    expect(html).toContain('value="atencao"');
  });
});

describe("marcação escrita à mão no index.html", () => {
  /**
   * Os campos do topo do cartão e os da prévia não são gerados pela tabela:
   * estão digitados no HTML. Um id trocado ali não quebra nenhum outro teste
   * — o `document` falso inventa qualquer seletor —, mas quebraria a tela de
   * verdade com "Cannot read properties of null".
   */
  test.each([
    "tg-blocos",
    "tg-max-itens",
    "tg-so-relevante",
    "tg-silencioso",
    "tg-previa",
    "tg-previa-status",
    "btn-previa-telegram",
    "btn-disp-telegram-completo",
  ])("a tela tem o elemento #%s", (elementoId) => {
    const html = fs.readFileSync("web/index.html", "utf8");

    expect(html).toContain(`id="${elementoId}"`);
  });
});

describe("componentes do cartão do Telegram", () => {
  /**
   * Os limiares usam `.campo` e `.grade-form`, como qualquer outro campo do
   * sistema: um número e um seletor têm de ter o mesmo tamanho e o mesmo
   * desenho aqui e na tela do provedor de IA. Uma classe própria de campo
   * criada só para este cartão é o que este teste impede de voltar.
   */
  test("os campos usam o componente padrão da tela, e não um próprio", () => {
    configuracoes.montarTelegram();
    const html = tela["#tg-blocos"].innerHTML;

    expect(html).toContain('class="campo"');
    expect(html).toContain('class="grade-form"');
    expect(html).not.toMatch(/class="[^"]*campo-tg/);
  });

  /**
   * O interruptor dos blocos já se chamou `.trilho` — o mesmo nome da barra de
   * alocação (`alocacao.js`, `posicoes.js`). A regra nova vinha depois no
   * arquivo e vencia, e toda barra de peso da carteira virou uma pílula de
   * 30px nas telas de Visão geral e de Posições.
   */
  test("nada redefine a classe da barra de alocação", () => {
    const css = fs.readFileSync("web/style.css", "utf8");
    const html = fs.readFileSync("web/index.html", "utf8");

    expect(css.match(/^\.trilho\s*\{/gm)).toHaveLength(1);
    expect(html).not.toContain('class="trilho"');
  });
});

describe("renderConfig e coletarConfig", () => {
  test("o que a tela coleta é aceito pelo validador do cadastro", () => {
    configuracoes.renderConfig(portfolio.carteiraVazia());

    const { config } = portfolio.atualizarConfig(configuracoes.coletarConfig());

    expect(config.telegram).toEqual(portfolio.TELEGRAM_PADRAO);
  });

  test("todo bloco dos padrões é coletado pela tela", () => {
    configuracoes.renderConfig(portfolio.carteiraVazia());

    const coletado = configuracoes.coletarConfig().config.telegram;

    expect(Object.keys(coletado).sort()).toEqual(Object.keys(portfolio.TELEGRAM_PADRAO).sort());
  });

  test("um limiar alterado na tela chega ao arquivo", () => {
    configuracoes.renderConfig(portfolio.carteiraVazia());
    tela["#tg-movimento-limiar-pct"].value = "7,5";
    tela["#tg-macro-ativo"].checked = false;

    const { config } = portfolio.atualizarConfig(configuracoes.coletarConfig());

    expect(config.telegram.movimento.limiar_pct).toBe(7.5);
    expect(config.telegram.macro.ativo).toBe(false);
    expect(JSON.parse(fs.readFileSync(`${temporario.dir}/portfolio.json`, "utf8"))
      .config.telegram.movimento.limiar_pct).toBe(7.5);
  });

  test("os marcos de calendário voltam à tela como texto e retornam como lista", () => {
    configuracoes.renderConfig(portfolio.carteiraVazia());

    expect(tela["#tg-calendario-rf-marcos-dias"].value).toBe("30, 15, 7, 3, 1");

    const { config } = portfolio.atualizarConfig(configuracoes.coletarConfig());
    expect(config.telegram.calendario_rf.marcos_dias).toEqual([30, 15, 7, 3, 1]);
  });

  test("o resumo do bloco recolhido mostra os limiares com a unidade", () => {
    configuracoes.renderConfig(portfolio.carteiraVazia());

    expect(tela["#tg-movimento-resumo"].textContent)
      .toBe("limiar 3% · peso mín. 3% · máx. 3");
    expect(tela["#tg-calendario-rf-resumo"].textContent)
      .toBe("marcos 30, 15, 7, 3, 1 · máx. 2");
    expect(tela["#tg-alertas-resumo"].textContent)
      .toBe("severidade atenção ou acima · máx. 3");
    expect(tela["#tg-resumo-ia-resumo"].textContent).toBe("às sex");
    expect(tela["#tg-indicadores-resumo"].textContent)
      .toBe("P/VP mín. 0,85 · P/VP máx. 1,15 · DY mín. 8%");
  });

  test("o resumo acompanha o que está sendo digitado", () => {
    /**
     * Sem o ouvinte de `input`, recolher um bloco recém-editado mostraria o
     * valor antigo até salvar e recarregar a tela.
     */
    configuracoes.montarTelegram();
    configuracoes.renderConfig(portfolio.carteiraVazia());
    tela["#tg-movimento-limiar-pct"].value = "8";

    tela["#tg-blocos"].ouvintes.input();

    expect(tela["#tg-movimento-resumo"].textContent).toContain("limiar 8%");
  });

  test("os dias da semana saem das caixas marcadas", () => {
    configuracoes.renderConfig(portfolio.carteiraVazia());
    const caixas = tela["#tg-resumo-ia-dias-semana"].filhos;
    caixas[0].checked = true;

    const { config } = portfolio.atualizarConfig(configuracoes.coletarConfig());

    expect(config.telegram.resumo_ia.dias_semana).toEqual([0, 4]);
  });
});
