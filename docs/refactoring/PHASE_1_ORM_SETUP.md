# Fase 1: Configuração de ORM e Alembic

**Duração**: 2-3 dias  
**Objetivo**: Estabelecer a infraestrutura de persistência com SQLAlchemy 2.x e Alembic, sem alterar lógica de negócio  
**Saída**: Models ORM, engine, session factory e primeira migração prontos

---

## Contexto

Hoje a persistência é feita com SQL manual direto em `SQLiteSessionStore`. A Fase 1 prepara a camada ORM para que a Fase 2 possa migrar tabelas de uma em uma.

### Não muda nesta fase
- Nenhum endpoint da API
- Nenhuma lógica de negócio
- JobService continua usando o repositório antigo

### Muda nesta fase
- Dependências do projeto (SQLAlchemy 2.x + Alembic)
- Estrutura de diretórios (`backend/app/db/`)
- Configuração de engine e session factory

---

## Estrutura de Diretórios Alvo

```
backend/app/
├── db/
│   ├── __init__.py
│   ├── models.py          # Modelos ORM (classes declarativas)
│   ├── config.py          # Engine, session factory, declarative base
│   ├── migration_utils.py # Helpers para migração incremental
│   └── migrations/        # Alembic migrations (gerado automaticamente)
│       ├── alembic.ini
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_initial_schema.py
├── repositories/
│   ├── session_store.py   # Mantém lógica de persistência manual por agora
│   └── ...
├── services/
│   └── jobs.py            # Mantém JobService como está
└── ...
```

---

## Etapas Executáveis

### 1.1 Instalar dependências

```bash
cd backend
pip install sqlalchemy==2.0.23 alembic==1.13.0
pip freeze > requirements.txt
```

**Validação**: `pip list | grep -i sqlalchemy`

---

### 1.2 Criar estrutura de configuração

**Arquivo**: `backend/app/db/config.py`

```python
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.settings import settings

# Base para todos os modelos ORM
Base = declarative_base()

# Engine - continua com SQLite local
def get_engine():
    db_url = f"sqlite:///{settings.sessions_db_path}"
    return create_engine(
        db_url,
        connect_args={"timeout": 30, "check_same_thread": False},
        echo=False,  # Mude para True para debug SQL
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    """Dependency injection para sessões do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Validação**: `python -c "from app.db.config import Base, engine; print('OK')"` (sem erro)

---

### 1.3 Criar modelos ORM

**Arquivo**: `backend/app/db/models.py`

```python
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.config import Base

class SessionORM(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    session_code = Column(String, nullable=False, unique=True)
    query = Column(String, nullable=False)
    selected_track_json = Column(Text, nullable=True)
    track_title = Column(String, nullable=True)
    artist = Column(String, nullable=True)
    target_stems_json = Column(String, nullable=False)
    state = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=False)
    stems_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    eta_seconds = Column(Integer, nullable=True)
    separation_device = Column(String, nullable=True)
    master_metrics_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    mix_states = relationship("SessionMixStateORM", back_populates="session", cascade="all, delete-orphan")
    exports = relationship("ExportJobORM", back_populates="session", cascade="all, delete-orphan")
    events = relationship("SessionEventORM", back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_sessions_created_at", "created_at"),
        Index("idx_sessions_state", "state"),
    )

class SessionMixStateORM(Base):
    __tablename__ = "session_mix_state"
    
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = relationship("SessionORM", back_populates="mix_states")

class ExportJobORM(Base):
    __tablename__ = "export_jobs"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    preset = Column(String, nullable=False)
    format = Column(String, nullable=False)
    state = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    output_json = Column(Text, nullable=False, default="[]")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = relationship("SessionORM", back_populates="exports")
    
    __table_args__ = (
        Index("idx_export_jobs_session_created", "session_id", "created_at"),
    )

class SessionEventORM(Base):
    __tablename__ = "session_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    stage = Column(String, nullable=False)
    level = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=False)
    
    session = relationship("SessionORM", back_populates="events")
    
    __table_args__ = (
        Index("idx_session_events_ts", "session_id", "ts"),
    )
```

**Validação**: `python -c "from app.db.models import SessionORM, SessionMixStateORM, ExportJobORM, SessionEventORM; print('OK')"` (sem erro)

---

### 1.4 Inicializar Alembic

```bash
cd backend
alembic init migrations
```

Isso cria `backend/migrations/` com estrutura padrão.

**Arquivo a editar**: `backend/alembic.ini`

```ini
# Mude a linha sqlalchemy.url para:
sqlalchemy.url = sqlite:///../storage/sessions.db
```

**Arquivo a editar**: `backend/migrations/env.py`

```python
# Na seção de imports, adicione:
from app.db.models import Base  # importa os modelos ORM
from app.db.config import engine

# Na funcao run_migrations_offline(), substitua:
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.sessions_db_path}")

# Na funcao run_migrations_online(), substitua target_metadata:
target_metadata = Base.metadata
```

**Validação**: `cd backend && alembic current` (deve retornar "No current revision" ou similar)

---

### 1.5 Gerar migração inicial

```bash
cd backend
alembic revision --autogenerate -m "0001_initial_schema"
```

Isso gera `backend/migrations/versions/0001_initial_schema.py` a partir dos modelos.

**Validação**: 
- Arquivo criado: `ls migrations/versions/*.py`
- Conteúdo sensato: `cat migrations/versions/0001_*.py | head -50`

---

### 1.6 Aplicar migração

```bash
cd backend
alembic upgrade head
```

Isso cria/sincroniza o schema do SQLite com os modelos ORM.

**Validação**: 
- Sem erro de SQL
- `sqlite3 ../storage/sessions.db ".tables"` mostra as tabelas

---

## Checklist de Conclusão da Fase 1

- [ ] SQLAlchemy 2.x + Alembic instalado (`pip list`)
- [ ] `backend/app/db/config.py` criado e importável
- [ ] `backend/app/db/models.py` criado com 4 models (Session, MixState, Export, Event)
- [ ] `backend/alembic.ini` configurado para SQLite
- [ ] `backend/alembic/env.py` aponta para models ORM
- [ ] Primeira migração gerada (`0001_initial_schema.py`)
- [ ] `alembic upgrade head` executa sem erro
- [ ] `sqlite3 ../storage/sessions.db ".tables"` mostra tabelas esperadas
- [ ] Backend ainda compila: `python -m compileall app` (sem erro)
- [ ] Smoke test legado de SessionStore ainda passa

---

## Próximas Fases

Fase 2 vai reimplementar o `SessionRepository` para usar os modelos ORM, mantendo a interface pública igual. Isso permite que `JobService` continue funcionar sem mudança enquanto migramos a persistência.

---

## Recursos Úteis

- SQLAlchemy 2.0 Docs: https://docs.sqlalchemy.org/
- Alembic Docs: https://alembic.sqlalchemy.org/
- ORM Patterns: https://docs.sqlalchemy.org/en/20/orm/
