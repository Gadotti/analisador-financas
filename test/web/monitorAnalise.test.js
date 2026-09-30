/**
 * web/js/monitorAnalise.js — quando a tela se atualiza sozinha e quando só avisa.
 *
 * Nenhum DOM nem rede: a consulta de versão, o redesenho e o "usuário ocupado"
 * entram por parâmetro, e o relógio é o do Jest.
 */

import { jest } from "@jest/globals";

let criarMonitorAnalise;
let iniciarVigia;

beforeAll(async () => {
  ({ criarMonitorAnalise, iniciarVigia } = await import("../../web/js/monitorAnalise.js"));
});

const versao = (v) => ({ versao: v, atualizada_em: v ? "2026-09-30T12:32:00.000Z" : null });

/** Monta um monitor com um "disco" cuja versão o teste controla. */
function cenario({ ocupado = false, versaoInicial = "v1" } = {}) {
  const disco = { versao: versaoInicial, falhar: false };
  const chamadas = { aplicar: 0, avisos: [], sozinho: [] };
  const ctx = { ocupado };

  const monitor = criarMonitorAnalise({
    consultarVersao: async () => {
      if (disco.falhar) throw new Error("rede fora");
      return versao(disco.versao);
    },
    aplicar: async () => {
      chamadas.aplicar += 1;
    },
    ocupado: () => ctx.ocupado,
    avisar: (aviso) => chamadas.avisos.push(aviso),
    aoAplicarSozinho: (info) => chamadas.sozinho.push(info),
  });
  return { monitor, disco, chamadas, ctx };
}

describe("criarMonitorAnalise.verificar", () => {
  test("a primeira leitura só anota a versão: não redesenha nem avisa", async () => {
    const { monitor, chamadas } = cenario();
    await monitor.verificar();
    expect(chamadas.aplicar).toBe(0);
    expect(chamadas.avisos).toEqual([]);
  });

  test("versão igual à da tela não faz nada", async () => {
    const { monitor, chamadas } = cenario();
    await monitor.registrar();
    await monitor.verificar();
    expect(chamadas.aplicar).toBe(0);
    expect(chamadas.sozinho).toEqual([]);
  });

  test("versão nova com a tela livre aplica em silêncio e comunica uma vez", async () => {
    const { monitor, disco, chamadas } = cenario();
    await monitor.registrar();

    disco.versao = "v2";
    await monitor.verificar();
    await monitor.verificar(); // já está na tela: não repete

    expect(chamadas.aplicar).toBe(1);
    expect(chamadas.sozinho).toHaveLength(1);
    expect(chamadas.sozinho[0].versao).toBe("v2");
    expect(chamadas.avisos.at(-1)).toBeNull();
  });

  test("versão nova com o usuário ocupado só avisa e não redesenha", async () => {
    const { monitor, disco, chamadas, ctx } = cenario({ ocupado: true });
    await monitor.registrar();

    disco.versao = "v2";
    await monitor.verificar();

    expect(chamadas.aplicar).toBe(0);
    expect(chamadas.avisos.at(-1)).toMatchObject({ versao: "v2" });
    expect(monitor.temPendente()).toBe(true);

    ctx.ocupado = false;
    await monitor.verificar();
    expect(chamadas.aplicar).toBe(1);
    expect(monitor.temPendente()).toBe(false);
    expect(chamadas.avisos.at(-1)).toBeNull();
  });

  test("a primeira análise que aparece (antes não havia nenhuma) é aplicada", async () => {
    const { monitor, disco, chamadas } = cenario({ versaoInicial: null });
    await monitor.registrar();

    disco.versao = "v1";
    await monitor.verificar();
    expect(chamadas.aplicar).toBe(1);
  });

  test("arquivo que sumiu (versão nula) é ignorado", async () => {
    const { monitor, disco, chamadas } = cenario();
    await monitor.registrar();

    disco.versao = null;
    await monitor.verificar();
    expect(chamadas.aplicar).toBe(0);
  });

  test("falha de rede não derruba o vigia e o ciclo seguinte se recupera", async () => {
    const { monitor, disco, chamadas } = cenario();
    await monitor.registrar();

    disco.falhar = true;
    disco.versao = "v2";
    await expect(monitor.verificar()).resolves.toBeUndefined();
    expect(chamadas.aplicar).toBe(0);

    disco.falhar = false;
    await monitor.verificar();
    expect(chamadas.aplicar).toBe(1);
  });

  test("falha ao redesenhar não marca a versão como vista: tenta de novo", async () => {
    const disco = { versao: "v1" };
    let tentativas = 0;
    const monitor = criarMonitorAnalise({
      consultarVersao: async () => versao(disco.versao),
      aplicar: async () => {
        tentativas += 1;
        if (tentativas === 1) throw new Error("GET /api/analise falhou");
      },
      ocupado: () => false,
      avisar: () => {},
    });
    await monitor.registrar();

    disco.versao = "v2";
    await monitor.verificar();
    await monitor.verificar();
    expect(tentativas).toBe(2);
  });

  test("não consulta em paralelo: uma verificação em curso absorve as demais", async () => {
    let consultas = 0;
    let liberar;
    const monitor = criarMonitorAnalise({
      consultarVersao: () => {
        consultas += 1;
        return new Promise((resolve) => {
          liberar = () => resolve(versao("v1"));
        });
      },
      aplicar: async () => {},
      ocupado: () => false,
      avisar: () => {},
    });

    const primeira = monitor.verificar();
    await monitor.verificar();
    expect(consultas).toBe(1);
    liberar();
    await primeira;
  });
});

describe("criarMonitorAnalise.registrar", () => {
  test("anota a versão da tela e desfaz um aviso pendente", async () => {
    const { monitor, disco, chamadas } = cenario({ ocupado: true });
    await monitor.registrar();
    disco.versao = "v2";
    await monitor.verificar();
    expect(monitor.temPendente()).toBe(true);

    await monitor.registrar(); // a própria interface acabou de gravar v2
    expect(monitor.temPendente()).toBe(false);
    expect(chamadas.avisos.at(-1)).toBeNull();
  });

  test("uma falha na consulta não sobe — o carregamento inicial segue", async () => {
    const { monitor, disco } = cenario();
    disco.falhar = true;
    await expect(monitor.registrar()).resolves.toBeUndefined();
  });
});

describe("criarMonitorAnalise.aplicarPendente", () => {
  test("aplica a versão avisada mesmo com o usuário ocupado e esconde a pílula", async () => {
    const { monitor, disco, chamadas } = cenario({ ocupado: true });
    await monitor.registrar();
    disco.versao = "v2";
    await monitor.verificar();

    await monitor.aplicarPendente();
    expect(chamadas.aplicar).toBe(1);
    expect(monitor.temPendente()).toBe(false);
    expect(chamadas.avisos.at(-1)).toBeNull();

    await monitor.verificar();
    expect(chamadas.aplicar).toBe(1); // v2 já está na tela
  });

  test("sem pendência consulta o disco; sem análise nenhuma, não faz nada", async () => {
    const { monitor, chamadas } = cenario({ versaoInicial: null });
    await monitor.aplicarPendente();
    expect(chamadas.aplicar).toBe(0);
  });
});

describe("iniciarVigia", () => {
  function ambienteFalso(oculto = false) {
    const ouvintes = {};
    const alvo = (extra = {}) => ({
      ...extra,
      addEventListener: (nome, fn) => {
        ouvintes[nome] = fn;
      },
      removeEventListener: (nome) => {
        delete ouvintes[nome];
      },
    });
    return { ouvintes, documento: alvo({ hidden: oculto }), janela: alvo() };
  }

  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test("consulta a cada intervalo enquanto a aba está à vista", () => {
    const monitor = { verificar: jest.fn() };
    const { documento, janela } = ambienteFalso();
    iniciarVigia(monitor, { intervaloMs: 60_000, documento, janela });

    jest.advanceTimersByTime(180_000);
    expect(monitor.verificar).toHaveBeenCalledTimes(3);
  });

  test("não consulta com a aba em segundo plano", () => {
    const monitor = { verificar: jest.fn() };
    const { documento, janela } = ambienteFalso(true);
    iniciarVigia(monitor, { intervaloMs: 60_000, documento, janela });

    jest.advanceTimersByTime(180_000);
    expect(monitor.verificar).not.toHaveBeenCalled();
  });

  test("consulta na hora ao voltar para a aba ou focar a janela", () => {
    const monitor = { verificar: jest.fn() };
    const { documento, janela, ouvintes } = ambienteFalso();
    iniciarVigia(monitor, { documento, janela });

    ouvintes.visibilitychange();
    ouvintes.focus();
    expect(monitor.verificar).toHaveBeenCalledTimes(2);
  });

  test("a aba ficar oculta não dispara consulta", () => {
    const monitor = { verificar: jest.fn() };
    const { documento, janela, ouvintes } = ambienteFalso(true);
    iniciarVigia(monitor, { documento, janela });

    ouvintes.visibilitychange();
    expect(monitor.verificar).not.toHaveBeenCalled();
  });

  test("a função devolvida desliga o relógio e os ouvintes", () => {
    const monitor = { verificar: jest.fn() };
    const { documento, janela, ouvintes } = ambienteFalso();
    const parar = iniciarVigia(monitor, { intervaloMs: 60_000, documento, janela });

    parar();
    jest.advanceTimersByTime(180_000);
    expect(monitor.verificar).not.toHaveBeenCalled();
    expect(ouvintes).toEqual({});
  });
});
