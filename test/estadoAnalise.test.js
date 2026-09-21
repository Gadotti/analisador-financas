import {
  atualizarFase,
  criarEstadoAnalise,
  finalizarComErro,
  finalizarComSucesso,
  iniciar,
  paraApi,
} from "../src/server/estadoAnalise.js";

test("estado inicial não tem execução nem erro", () => {
  const estado = criarEstadoAnalise();
  expect(paraApi(estado)).toEqual({
    em_andamento: false,
    com_ia: null,
    iniciada_em: null,
    fase: null,
    ultimo_erro: null,
    ultimo_erro_em: null,
  });
});

test("iniciar marca em_andamento, com_ia e o instante de início", () => {
  const estado = criarEstadoAnalise();
  iniciar(estado, { comIa: true });
  const api = paraApi(estado);
  expect(api.em_andamento).toBe(true);
  expect(api.com_ia).toBe(true);
  expect(api.iniciada_em).not.toBeNull();
  expect(api.fase).toBeNull();
});

test("atualizarFase reflete a última linha de progresso do script", () => {
  const estado = criarEstadoAnalise();
  iniciar(estado, { comIa: true });
  atualizarFase(estado, "[1/3] Carregando carteira e cotações...");
  expect(paraApi(estado).fase).toBe("[1/3] Carregando carteira e cotações...");
});

test("finalizarComSucesso limpa em_andamento e a fase", () => {
  const estado = criarEstadoAnalise();
  iniciar(estado, { comIa: false });
  atualizarFase(estado, "[1/3] ...");
  finalizarComSucesso(estado);
  const api = paraApi(estado);
  expect(api.em_andamento).toBe(false);
  expect(api.fase).toBeNull();
  expect(api.ultimo_erro).toBeNull();
});

test("finalizarComErro guarda a mensagem e quando ela aconteceu", () => {
  const estado = criarEstadoAnalise();
  iniciar(estado, { comIa: true });
  finalizarComErro(estado, "A análise excedeu o tempo limite.");
  const api = paraApi(estado);
  expect(api.em_andamento).toBe(false);
  expect(api.ultimo_erro).toBe("A análise excedeu o tempo limite.");
  expect(api.ultimo_erro_em).not.toBeNull();
});

test("iniciar uma nova execução limpa o erro da tentativa anterior", () => {
  const estado = criarEstadoAnalise();
  iniciar(estado, { comIa: true });
  finalizarComErro(estado, "falhou");
  iniciar(estado, { comIa: true });
  const api = paraApi(estado);
  expect(api.ultimo_erro).toBeNull();
  expect(api.ultimo_erro_em).toBeNull();
});
