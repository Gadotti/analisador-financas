import fs from "node:fs";

import { usuariosFile } from "../src/config/paths.js";
import {
  AutenticacaoError,
  configuracaoAuth,
  conferirCredenciais,
  criarOuAtualizarUsuario,
} from "../src/core/usuarios.js";
import { dataDirTemporario } from "./helpers/ambiente.js";

let ambiente;

beforeEach(() => {
  ambiente = dataDirTemporario();
});

afterEach(() => {
  ambiente.limpar();
});

describe("configuracaoAuth", () => {
  test("lança AutenticacaoError quando o arquivo ainda não existe", () => {
    expect(() => configuracaoAuth()).toThrow(AutenticacaoError);
    expect(() => configuracaoAuth()).toThrow(/criarLogin\.js/);
  });

  test("lança AutenticacaoError quando o arquivo existe mas não tem usuário nenhum", () => {
    fs.writeFileSync(usuariosFile(), JSON.stringify({ segredo_sessao: "x", usuarios: [] }), "utf8");
    expect(() => configuracaoAuth()).toThrow(AutenticacaoError);
  });

  test("lança AutenticacaoError quando falta o segredo de sessão", () => {
    fs.writeFileSync(
      usuariosFile(),
      JSON.stringify({ segredo_sessao: "", usuarios: [{ usuario: "a", senha_hash: "x:y" }] }),
      "utf8",
    );
    expect(() => configuracaoAuth()).toThrow(AutenticacaoError);
  });

  test("trata segredo_sessao e usuarios com tipo errado como ausentes", () => {
    fs.mkdirSync(ambiente.dir, { recursive: true });
    fs.writeFileSync(usuariosFile(), JSON.stringify({ segredo_sessao: 123, usuarios: "não é lista" }), "utf8");
    expect(() => configuracaoAuth()).toThrow(AutenticacaoError);
  });

  test("lança AutenticacaoError quando o arquivo não é um JSON válido", () => {
    fs.mkdirSync(ambiente.dir, { recursive: true });
    fs.writeFileSync(usuariosFile(), "isto não é json", "utf8");
    expect(() => configuracaoAuth()).toThrow(AutenticacaoError);
    expect(() => configuracaoAuth()).toThrow(/JSON válido/);
  });

  test("devolve os usuários e o segredo depois de criarOuAtualizarUsuario", () => {
    criarOuAtualizarUsuario("admin", "senha-123456");
    const config = configuracaoAuth();
    expect(config.segredo_sessao).toEqual(expect.any(String));
    expect(config.segredo_sessao.length).toBeGreaterThan(0);
    expect(config.usuarios).toEqual([{ usuario: "admin", senha_hash: expect.any(String) }]);
  });
});

describe("criarOuAtualizarUsuario", () => {
  test("cria o primeiro usuário e gera um segredo de sessão", () => {
    const resultado = criarOuAtualizarUsuario("admin", "senha-123456");
    expect(resultado).toEqual({ criado: true });

    const dados = JSON.parse(fs.readFileSync(usuariosFile(), "utf8"));
    expect(dados.usuarios).toHaveLength(1);
    expect(dados.segredo_sessao).toEqual(expect.any(String));
    expect(dados.segredo_sessao.length).toBeGreaterThan(0);
  });

  test("um segundo usuário se junta ao primeiro, sem removê-lo", () => {
    criarOuAtualizarUsuario("admin", "senha-123456");
    const resultado = criarOuAtualizarUsuario("convidado", "outra-senha");

    expect(resultado).toEqual({ criado: true });
    const dados = JSON.parse(fs.readFileSync(usuariosFile(), "utf8"));
    expect(dados.usuarios.map((u) => u.usuario).sort()).toEqual(["admin", "convidado"]);
  });

  test("preserva o mesmo segredo de sessão entre usuários — trocar derrubaria as sessões de todos", () => {
    criarOuAtualizarUsuario("admin", "senha-123456");
    const { segredo_sessao: primeiro } = JSON.parse(fs.readFileSync(usuariosFile(), "utf8"));

    criarOuAtualizarUsuario("convidado", "outra-senha");
    const { segredo_sessao: segundo } = JSON.parse(fs.readFileSync(usuariosFile(), "utf8"));

    expect(segundo).toBe(primeiro);
  });

  test("rodar de novo com o mesmo usuário troca a senha em vez de duplicar", () => {
    criarOuAtualizarUsuario("admin", "senha-antiga");
    const resultado = criarOuAtualizarUsuario("admin", "senha-nova");

    expect(resultado).toEqual({ criado: false });
    const dados = JSON.parse(fs.readFileSync(usuariosFile(), "utf8"));
    expect(dados.usuarios).toHaveLength(1);
    expect(conferirCredenciais(dados.usuarios, "admin", "senha-nova")).toBe("admin");
    expect(conferirCredenciais(dados.usuarios, "admin", "senha-antiga")).toBeNull();
  });
});

describe("conferirCredenciais", () => {
  const usuarios = [{ usuario: "admin", senha_hash: undefined }];

  beforeEach(() => {
    criarOuAtualizarUsuario("admin", "senha-correta");
    usuarios[0] = configuracaoAuth().usuarios[0];
  });

  test("usuário e senha corretos devolvem o nome do usuário", () => {
    expect(conferirCredenciais(usuarios, "admin", "senha-correta")).toBe("admin");
  });

  test("senha errada devolve null", () => {
    expect(conferirCredenciais(usuarios, "admin", "senha-errada")).toBeNull();
  });

  test("usuário inexistente devolve null", () => {
    expect(conferirCredenciais(usuarios, "fantasma", "senha-correta")).toBeNull();
  });

  test.each([
    [undefined, "senha-correta"],
    ["admin", undefined],
    [123, "senha-correta"],
    ["admin", null],
  ])("entradas que não são string (%p, %p) nunca lançam, devolvem null", (usuario, senha) => {
    expect(() => conferirCredenciais(usuarios, usuario, senha)).not.toThrow();
    expect(conferirCredenciais(usuarios, usuario, senha)).toBeNull();
  });
});
