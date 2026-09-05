import fs from "node:fs";

import { portfolioFile } from "../src/config/paths.js";
import * as portfolio from "../src/core/portfolio.js";
import { dataDirTemporario } from "./helpers/ambiente.js";

let ambiente;

beforeAll(() => {
  ambiente = dataDirTemporario();
});
afterAll(() => ambiente.limpar());
beforeEach(() => {
  fs.rmSync(portfolioFile(), { force: true });
});

const FII = { tipo: "fii", ticker: "mxrf11", quantidade: "100", preco_medio: "9,85" };
const CDB = {
  tipo: "cdb",
  banco: "Inter",
  valor_inicial: 10000,
  indexador: "cdi",
  taxa: 110,
  data_aplicacao: "2025-01-02",
  data_vencimento: "2027-01-04",
};

const TESOURO = {
  tipo: "tesouro",
  valor_inicial: 20000,
  indexador: "selic",
  taxa: 0.0949,
  data_aplicacao: "2025-01-02",
  data_vencimento: "2029-03-01",
};

describe("normalizar", () => {
  test("normaliza uma posição de renda variável", () => {
    const pos = portfolio.normalizar(FII);
    expect(pos).toMatchObject({
      tipo: "fii",
      ticker: "MXRF11",
      quantidade: 100,
      preco_medio: 9.85, // aceita vírgula decimal
      data_compra: null,
    });
    expect(pos.id).toMatch(/^[0-9a-f]{12}$/);
  });

  test("remove o sufixo .SA do ticker", () => {
    expect(portfolio.normalizar({ ...FII, ticker: "petr4.sa" }).ticker).toBe("PETR4");
  });

  test("normaliza um CDB e gera o nome padrão", () => {
    expect(portfolio.normalizar(CDB)).toMatchObject({
      indexador: "CDI",
      nome: "CDB Inter 110% do CDI",
      liquidez_diaria: false,
      pagamento_juros: "vencimento",
    });
  });

  test("aceita CDB com juros mensais", () => {
    const pos = portfolio.normalizar({ ...CDB, pagamento_juros: "MENSAL" });
    expect(pos.pagamento_juros).toBe("mensal");
  });

  test("preserva o id quando informado", () => {
    expect(portfolio.normalizar({ ...FII, id: "abc123" }).id).toBe("abc123");
  });

  test.each([
    ["tipo inválido", { ...FII, tipo: "cripto" }, /Tipo invalido/],
    ["indexador inválido", { ...CDB, indexador: "SELIC" }, /Indexador invalido/],
    ["pagamento de juros inválido", { ...CDB, pagamento_juros: "trimestral" }, /Pagamento de juros invalido/],
    ["ticker ausente", { tipo: "fii" }, /'ticker' e obrigatorio/],
    ["quantidade vazia", { ...FII, quantidade: "" }, /'quantidade' e obrigatorio/],
    ["banco em branco", { ...CDB, banco: "  " }, /'banco' e obrigatorio/],
    ["quantidade não numérica", { ...FII, quantidade: "muitas" }, /deve ser numerico/],
    ["preço negativo", { ...FII, preco_medio: -1 }, /deve ser >= 0/],
    ["valor inicial zerado", { ...CDB, valor_inicial: 0 }, /deve ser >= 0.01/],
    ["data em formato BR", { ...CDB, data_aplicacao: "02/01/2025" }, /use AAAA-MM-DD/],
    ["vencimento ausente", { ...CDB, data_vencimento: "" }, /'data_vencimento' e obrigatorio/],
    ["vencimento antes da aplicação", { ...CDB, data_vencimento: "2024-01-01" }, /anterior a data de aplicacao/],
  ])("rejeita %s", (_titulo, entrada, mensagem) => {
    expect(() => portfolio.normalizar(entrada)).toThrow(mensagem);
    expect(() => portfolio.normalizar(entrada)).toThrow(portfolio.ValidacaoError);
  });

  test("aceita vencimento igual à aplicação", () => {
    const pos = portfolio.normalizar({ ...CDB, data_vencimento: CDB.data_aplicacao });
    expect(pos.data_vencimento).toBe("2025-01-02");
  });
});

describe("rotuloTaxa e descricao", () => {
  test.each([
    [{ indexador: "CDI", taxa: 110 }, "110% do CDI"],
    [{ indexador: "PRE", taxa: 12.5 }, "12.5% a.a."],
    [{ indexador: "IPCA", taxa: 6.5 }, "IPCA + 6.5% a.a."],
    [{ indexador: "SELIC", taxa: 0.0949 }, "SELIC + 0.0949% a.a."],
  ])("descreve %o como %s", (titulo, esperado) => {
    expect(portfolio.rotuloTaxa(titulo)).toBe(esperado);
  });

  test.each([
    [{ tipo: "acao", ticker: "PETR4" }, "PETR4"],
    [{ tipo: "cdb", banco: "Inter" }, "CDB Inter"],
    [{ tipo: "cdb", nome: "CDB X", banco: "Y" }, "CDB X"],
    [{ tipo: "tesouro", nome: "Tesouro Selic 2029" }, "Tesouro Selic 2029"],
    [{ tipo: "tesouro" }, "Tesouro Direto"],
  ])("resolve a descrição de %o", (pos, esperado) => {
    expect(portfolio.descricao(pos)).toBe(esperado);
  });
});

describe("persistência e CRUD", () => {
  test("cria uma carteira vazia quando o arquivo não existe", () => {
    const carteira = portfolio.load();
    expect(carteira.posicoes).toEqual([]);
    expect(carteira.versao).toBe(portfolio.VERSAO);
    expect(carteira.config.limite_fgc).toBe(250000);
    expect(fs.existsSync(portfolioFile())).toBe(true);
  });

  test("completa a config com os padrões ao carregar", () => {
    fs.writeFileSync(
      portfolioFile(),
      JSON.stringify({ versao: 2, posicoes: [], config: { max_fatos: 2 } }),
    );
    const carteira = portfolio.load();
    expect(carteira.config.max_fatos).toBe(2);
    expect(carteira.config.alerta_prejuizo_pct).toBe(15);
    expect(carteira.perfil).toBe("");
  });

  test("recusa um arquivo corrompido com mensagem clara", () => {
    fs.writeFileSync(portfolioFile(), "{ nao é json");
    expect(() => portfolio.load()).toThrow(/Carteira corrompida/);
  });

  test("adiciona, atualiza e remove posições", () => {
    const nova = portfolio.adicionar(FII);
    expect(portfolio.load().posicoes).toHaveLength(1);

    const editada = portfolio.atualizar(nova.id, { ...FII, quantidade: 250 });
    expect(editada.id).toBe(nova.id);
    expect(portfolio.load().posicoes[0].quantidade).toBe(250);

    portfolio.remover(nova.id);
    expect(portfolio.load().posicoes).toHaveLength(0);
  });

  test("ignora o id enviado ao adicionar, gerando um novo", () => {
    expect(portfolio.adicionar({ ...FII, id: "id-do-cliente" }).id).not.toBe("id-do-cliente");
  });

  test("erra ao atualizar ou remover posição inexistente", () => {
    expect(() => portfolio.atualizar("xxx", FII)).toThrow(/nao encontrada/);
    expect(() => portfolio.remover("xxx")).toThrow(/nao encontrada/);
  });

  test("grava atomicamente e não deixa arquivo temporário", () => {
    portfolio.adicionar(FII);
    expect(fs.existsSync(`${portfolioFile()}.tmp`)).toBe(false);
  });

  test("atualiza perfil e apenas as chaves conhecidas da config", () => {
    const carteira = portfolio.atualizarConfig({
      perfil: "  Foco em renda  ",
      config: { alerta_prejuizo_pct: "20", chave_invalida: 1 },
    });
    expect(carteira.perfil).toBe("Foco em renda");
    expect(carteira.config.alerta_prejuizo_pct).toBe(20);
    expect(carteira.config).not.toHaveProperty("chave_invalida");
  });

  test("rejeita valores de config negativos", () => {
    expect(() => portfolio.atualizarConfig({ config: { limite_fgc: -1 } })).toThrow(/deve ser >= 0/);
  });
});

describe("migração do formato antigo", () => {
  test("converte tickers soltos e mantém o perfil", () => {
    fs.writeFileSync(
      portfolioFile(),
      JSON.stringify({
        versao: 1,
        profile: "perfil antigo",
        tickers: ["HGLG11", "XPML11"],
        max_fatos: 3,
      }),
    );

    const carteira = portfolio.load();
    expect(carteira.versao).toBe(2);
    expect(carteira.perfil).toBe("perfil antigo");
    expect(carteira.posicoes.map((p) => p.ticker)).toEqual(["HGLG11", "XPML11"]);
    expect(carteira.posicoes[0].quantidade).toBe(0);
    expect(carteira.config.max_fatos).toBe(3);
  });

  test("descarta posições inválidas em vez de falhar a migração", () => {
    const carteira = portfolio.migrar({
      posicoes: [{ tipo: "fii", ticker: "OK11", quantidade: 1, preco_medio: 1 }, { tipo: "??" }],
    });
    expect(carteira.posicoes).toHaveLength(1);
  });
});

describe("tickers", () => {
  test("devolve tickers únicos de renda variável, na ordem de cadastro", () => {
    const carteira = {
      posicoes: [
        { tipo: "fii", ticker: "MXRF11" },
        { tipo: "cdb", banco: "Inter" },
        { tipo: "acao", ticker: "PETR4" },
        { tipo: "fii", ticker: "MXRF11" },
      ],
    };
    expect(portfolio.tickers(carteira)).toEqual(["MXRF11", "PETR4"]);
  });
});

describe("títulos do Tesouro Direto", () => {
  test("normaliza um título e gera o nome comercial do papel", () => {
    expect(portfolio.normalizar(TESOURO)).toMatchObject({
      tipo: "tesouro",
      indexador: "SELIC",
      taxa: 0.0949,
      nome: "Tesouro Selic 2029",
      pagamento_juros: "vencimento",
    });
  });

  test.each([
    [{ indexador: "pre", pagamento_juros: "vencimento" }, "Tesouro Prefixado 2029"],
    [{ indexador: "ipca", pagamento_juros: "vencimento" }, "Tesouro IPCA+ 2029"],
    [
      { indexador: "ipca", pagamento_juros: "semestral" },
      "Tesouro IPCA+ 2029 com Juros Semestrais",
    ],
  ])("nomeia %o como %s", (campos, esperado) => {
    expect(portfolio.normalizar({ ...TESOURO, ...campos }).nome).toBe(esperado);
  });

  test("preserva o nome informado pelo usuário", () => {
    const pos = portfolio.normalizar({ ...TESOURO, nome: "NTN-B Principal 2029" });
    expect(pos.nome).toBe("NTN-B Principal 2029");
  });

  test("não exige banco emissor — quem responde é o Tesouro Nacional", () => {
    const pos = portfolio.normalizar(TESOURO);
    expect(pos.banco).toBeUndefined();
    expect(portfolio.emissorDe(pos)).toBe("Tesouro Nacional");
  });

  test.each([
    ["CDI, que é indexador de CDB", { indexador: "CDI" }, /Indexador invalido/],
    ["cupom mensal, que é de CDB", { pagamento_juros: "mensal" }, /Pagamento de juros invalido/],
    ["valor aplicado zerado", { valor_inicial: 0 }, /deve ser >= 0.01/],
    ["vencimento antes da aplicação", { data_vencimento: "2024-01-01" }, /anterior a data de aplicacao/],
  ])("rejeita %s", (_titulo, campos, mensagem) => {
    expect(() => portfolio.normalizar({ ...TESOURO, ...campos })).toThrow(mensagem);
  });

  test("o CDB continua sem aceitar Selic nem cupom semestral", () => {
    expect(() => portfolio.normalizar({ ...CDB, indexador: "SELIC" })).toThrow(/Indexador invalido/);
    expect(() => portfolio.normalizar({ ...CDB, pagamento_juros: "semestral" })).toThrow(
      /Pagamento de juros invalido/,
    );
  });

  test("grava e relê um título junto com as demais posições", () => {
    portfolio.adicionar(FII);
    const titulo = portfolio.adicionar(TESOURO);

    const carteira = portfolio.load();
    expect(carteira.posicoes).toHaveLength(2);
    expect(carteira.posicoes[1]).toMatchObject({ id: titulo.id, tipo: "tesouro" });
    expect(portfolio.tickers(carteira)).toEqual(["MXRF11"]);
  });
});

describe("taxa do Tesouro é opcional", () => {
  test("aceita título sem taxa — ela vem do pregão da compra", () => {
    const { taxa, ...resto } = TESOURO;
    const pos = portfolio.normalizar(resto);

    expect(pos.taxa).toBeNull();
    expect(pos.nome).toBe("Tesouro Selic 2029");
  });

  test("taxa informada é preservada e prevalece sobre a busca", () => {
    expect(portfolio.normalizar({ ...TESOURO, taxa: "0,0949" }).taxa).toBe(0.0949);
  });

  test("o CDB continua exigindo a taxa, que está no contrato", () => {
    const { taxa, ...semTaxa } = CDB;
    expect(() => portfolio.normalizar(semTaxa)).toThrow(/'taxa' e obrigatorio/);
  });

  test("rotuloTaxa avisa quando a taxa ainda não foi buscada", () => {
    expect(portfolio.rotuloTaxa({ indexador: "PRE", taxa: null })).toBe("taxa a buscar");
  });

  test("Tesouro Selic não aceita cupom — o papel só paga no vencimento", () => {
    expect(() =>
      portfolio.normalizar({ ...TESOURO, pagamento_juros: "semestral" }),
    ).toThrow(/Tesouro Selic paga tudo no vencimento/);
  });

  test.each([
    ["PRE", "semestral"],
    ["IPCA", "semestral"],
    ["IPCA", "vencimento"],
  ])("%s com pagamento %s continua válido", (indexador, pagamento_juros) => {
    const pos = portfolio.normalizar({ ...TESOURO, indexador, pagamento_juros });
    expect(pos.pagamento_juros).toBe(pagamento_juros);
  });
});
