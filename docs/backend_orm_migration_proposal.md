# Proposta: migrar a persistencia do backend para ORM leve

## Contexto

Hoje o backend usa SQLite de forma manual em um repositório central, com SQL direto, serialização JSON e schema criado no proprio codigo. Isso funciona bem para o MVP, mas tende a ficar caro de manter quando o projeto crescer em volume de regras, novas tabelas e relacoes entre entidades.

O objetivo desta proposta nao e trocar o SQLite. O objetivo e trocar o acesso manual ao banco por uma camada de persistencia mais organizada, mantendo SQLite como storage local por enquanto e deixando uma trilha clara para evoluir depois, se necessario, para PostgreSQL.

## Recomendacao

Adotar SQLAlchemy 2.x como camada de ORM e Alembic para migracoes.

Motivos principais:

- reduz o tamanho do codigo de acesso a dados espalhado em classes grandes;
- separa melhor dominio, persistencia e serializacao;
- torna novas entidades e relacoes mais previsiveis de manter;
- facilita testes de repositorio e evolucao do schema;
- preserva a opcao de continuar com SQLite local sem custo de infraestrutura extra.

## O que eu nao faria

- Nao migraria para um ORM completo e pesado so por padrao.
- Nao trocaria para uma abordagem Active Record acoplada aos modelos de dominio.
- Nao quebraria os endpoints atuais durante a transicao.

## Desenho proposto

### Camadas

- Modelos ORM: representam tabelas e relacoes.
- Schemas Pydantic: continuam como contrato da API.
- Repositorios: concentram consultas, salvamento e filtros.
- Servicos: mantem regras de negocio e orquestracao.

### Principios

- manter a API publica estavel;
- migrar tabela por tabela, nao tudo de uma vez;
- evitar SQL cru fora dos repositorios;
- usar transacoes explicitas onde houver multiplas escritas coerentes.

## Escopo da migracao

### Primeira fase

- `sessions`
- `session_mix_state`
- `export_jobs`
- `session_events`
- contador ou geracao de `session_code`

Essas tabelas cobrem o fluxo atual de processamento, biblioteca, estado de mix e exportacao.

### Segunda fase

- entidades auxiliares que surgirem com busca, analise e historico;
- relacoes adicionais entre sessao, artefatos e eventos;
- indices e migracoes de performance.

## Plano de entrega

### Fase 1: infra de persistencia

1. Introduzir SQLAlchemy 2.x e Alembic.
2. Criar engine, session factory e base declarativa.
3. Migrar o schema atual para modelos ORM equivalentes.
4. Criar a primeira migracao Alembic a partir do schema atual.

### Fase 2: repositorios paralelos

1. Reescrever o repositório de sessoes para usar ORM.
2. Manter assinaturas publicas o mais proximas possivel do que existe hoje.
3. Preservar os endpoints atuais durante a transicao.
4. Validar leitura e escrita com a mesma base SQLite local.

### Fase 3: simplificacao do dominio

1. Extrair utilitarios de serializacao JSON para funcoes pequenas e testaveis.
2. Separar conversao entre ORM e schemas Pydantic.
3. Remover dependencias diretas de `sqlite3` do codigo de negocio.

### Fase 4: preparacao para crescimento

1. Consolidar migracoes Alembic.
2. Revisar indices e campos opcionais a medida que novas features entrarem.
3. Avaliar troca para PostgreSQL apenas se houver necessidade real de concorrencia, multiusuario ou volume maior.

## Criterios de aceite

- O backend continua funcionando com SQLite local.
- Reiniciar a aplicacao nao perde historico de sessoes.
- Os endpoints atuais continuam compatíveis durante a migracao.
- O codigo de persistencia fica menor e mais modular que a implementacao manual atual.
- Novas tabelas e campos passam a ser adicionados por migracao, nao por `CREATE TABLE` espalhado no runtime.

## Riscos

- Curva de aprendizado inicial para quem nao usa ORM no backend.
- Migracao mal fatiada pode introduzir regressao em leitura ou escrita.
- Se a equipe tentar usar ORM para esconder regra de negocio, a base pode ficar mais confusa em vez de mais simples.

## Mitigacoes

- Fazer a migracao em etapas pequenas.
- Manter testes de repositorio e de API durante a transicao.
- Limitar o ORM ao acesso a dados, sem misturar regra de negocio nos modelos.

## Decisao pratica

Se a expectativa e continuar adicionando funcionalidades por muito tempo, eu faria a migracao agora. O custo inicial compensa porque evita ampliar uma classe de persistencia manual que ja esta virando um ponto concentrador de complexidade.

Se a intenção fosse congelar o escopo do backend, manter o SQLite manual ainda seria aceitavel. Mas, para este projeto, o caminho mais sustentavel e o ORM leve com migracoes.