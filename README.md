# Comunidade Escolar — EduConnect

Aplicação web educacional desenvolvida em Python com Flask, apresentada na interface como **EduConnect**. O projeto reúne áreas para alunos e professores, com acesso a cursos, acompanhamento de aulas, perfis e informações escolares.

O sistema está em desenvolvimento: combina funcionalidades integradas ao MySQL com telas e indicadores demonstrativos. O repositório ainda não inclui o esquema completo do banco de dados necessário para executar todos os recursos.

## Funcionalidades

### Acesso e cadastro

- Página inicial de apresentação da plataforma.
- Cadastro de alunos e professores.
- Login por apelido e senha, com redirecionamento conforme o perfil.
- Controle de sessão e logout.

### Área do aluno

- Consulta de cursos, capítulos e aulas vinculados ao banco de dados.
- Marcação e desmarcação de aulas concluídas, com cálculo de progresso.
- Consulta e edição do perfil, incluindo senha e foto.
- Processamento da foto com Pillow, redimensionamento para até 300 × 300 pixels e armazenamento como imagem JPEG em Base64.
- Preferências de tema, tamanho da fonte, alto contraste e tempo de sessão.
- Telas de calendário, desempenho e notificações, atualmente com dados demonstrativos.

### Área do professor

- Painel inicial, visualização de cursos, capítulos e indicadores.
- Telas de listagem e visualização de alunos, ainda com dados de exemplo ou conteúdo incompleto.
- Consulta do perfil e atualização de contato, especializações e senha.
- Tela de calendário.

A listagem de cursos do professor e a página de detalhes com estatísticas usam dados fictícios. Outras consultas, como o acesso a um curso e parte do perfil, utilizam o MySQL. A presença de uma tela ou preferência não significa que exista uma integração completa de envio de notificações, gestão de eventos ou geração de relatórios.

## Tecnologias

| Tecnologia | Uso |
| --- | --- |
| Python e Flask | Rotas, autenticação, sessões e respostas HTTP |
| Jinja2 | Renderização dos templates HTML pelo Flask |
| MySQL e MySQL Connector/Python | Persistência e consultas SQL |
| Pillow | Tratamento de fotos de perfil |
| HTML, CSS e JavaScript | Interface e interações no navegador |
| Font Awesome | Ícones carregados por CDN |
| Chart.js | Gráficos na tela de desempenho, carregados por CDN |

## Estrutura do projeto

```text
Comunidade-Escolar/
├── app.py                 # Aplicação Flask, rotas, consultas e regras de negócio
├── banco.sql              # Script parcial do banco de dados
├── Readme.md              # Documentação do projeto
└── view/
    ├── usuario/           # Templates públicos, login e cadastro
    ├── aluno/             # Templates da área do aluno
    └── professor/         # Templates da área do professor
```

O Flask utiliza `view/` como diretório de templates. O código também configura um diretório `static/`, mas ele não está presente no repositório analisado. Os estilos e scripts estão principalmente nos próprios templates.

## Como executar localmente

### 1. Preparar o ambiente Python

É necessário ter Python 3 com `pip` e um servidor MySQL acessível. O projeto não informa versões fixas das dependências nem inclui `requirements.txt`.

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install Flask mysql-connector-python Pillow
```

Os comandos usam diretamente o Python do ambiente virtual, sem necessidade de ativá-lo.

### 2. Configurar a conexão

Em `app.py`, ajuste os argumentos de `mysql.connector.connect()` na função `conectar()` para o seu ambiente local:

```python
host="localhost",
user="seu_usuario",
password="sua_senha",
database="comunidade_escolar",
port=3306
```

A configuração atual é feita diretamente no código; não há carregamento de arquivo `.env` implementado.

### 3. Preparar o banco de dados

**O arquivo `banco.sql` é parcial e não basta para executar o sistema completo.** Ele cria o banco `comunidade_escolar` e define apenas a tabela `eventos_calendario`.

Para utilizar esse script em uma instalação nova, execute primeiro o `CREATE DATABASE`, selecione o banco com `USE comunidade_escolar;` e só então execute o `CREATE TABLE`. O arquivo não inclui o comando `USE`, e o banco já existente exige ajuste do comando de criação.

As consultas de `app.py` também dependem das seguintes tabelas:

| Tabela | Finalidade |
| --- | --- |
| `usuarios` | Dados de acesso e perfis de alunos e professores |
| `cursos` | Informações dos cursos e vínculo com professores |
| `matricula` | Vínculo entre alunos e cursos |
| `capitulos_curso` | Organização dos capítulos de cada curso |
| `aulas` | Conteúdo das aulas de cada capítulo |
| `progresso_aulas` | Acessos e conclusões de aulas e capítulos |
| `notas` | Dados usados nas consultas de desempenho |
| `configuracoes` | Preferências dos usuários em JSON |
| `atividades_usuario` | Registro de atividades dos usuários |

Ao executar `python app.py`, a aplicação tenta criar `configuracoes` e `atividades_usuario` se houver conexão e permissão. As demais tabelas precisam ser obtidas de um esquema compatível ou implementadas conforme as consultas do código; suas definições não estão incluídas no repositório.

Existe também uma divergência a resolver: o perfil do professor consulta `matriculas`, enquanto outras rotas consultam `matricula`.

### 4. Iniciar a aplicação

Após configurar a conexão e disponibilizar o esquema necessário:

```powershell
.\.venv\Scripts\python.exe app.py
```

Acesse `http://127.0.0.1:5000` no navegador. Cadastre um aluno ou professor e use o apelido e a senha para entrar. As funcionalidades de cursos dependem de registros e vínculos no banco; o repositório não fornece uma carga inicial completa.

Recursos visuais externos, como ícones e gráficos por CDN, dependem de acesso à internet.

## Principais rotas

| Rota | Finalidade |
| --- | --- |
| `/` | Página inicial |
| `/cadastro` | Cadastro de aluno ou professor |
| `/login` e `/logout` | Entrada e saída da sessão |
| `/home_aluno` | Painel do aluno |
| `/cursos_aluno` | Cursos do aluno |
| `/cursos/<curso_id>` | Detalhes e capítulos de um curso |
| `/capitulo/<capitulo_id>` | Aulas de um capítulo |
| `/perfil_aluno` | Perfil do aluno |
| `/configuracoes_aluno` | Preferências do aluno |
| `/home_professor` | Painel do professor |
| `/seus_cursos` | Listagem demonstrativa de cursos do professor |
| `/acessar_curso/<curso_id>` | Consulta de curso e capítulos no banco |
| `/professor/alunos` | Tela de alunos, ainda incompleta |
| `/perfil_professor` | Perfil do professor |

## Estado atual e limitações

- O esquema SQL está incompleto e há divergência no nome da tabela de matrículas.
- Parte dos dados apresentados é fixa ou demonstrativa, inclusive em telas que também consultam o banco.
- A rota `/curso/python` referencia `professor/curso_python.html`, arquivo ausente no repositório.
- Existem templates públicos de eventos, contatos e políticas sem rotas correspondentes em `app.py`.
- O código contém credenciais de banco e chave de sessão fixas, armazena senhas sem hash e inicia o servidor com `debug=True`. Esses pontos precisam ser corrigidos antes de uma publicação em produção.
- Não há suíte de testes automatizados nem arquivo de dependências com versões fixadas no repositório.

Esta documentação foi elaborada pela leitura do código e dos templates. A execução completa com MySQL não foi validada.
