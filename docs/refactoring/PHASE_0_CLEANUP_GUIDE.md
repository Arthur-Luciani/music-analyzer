# Fase 0: Completar Cleanup (30 minutos)

**Objetivo**: Remover duplicate SQLiteSessionStore de jobs.py após extraction para repositories/

**Status**: 80% completo. SQLiteSessionStore já foi extraído. Falta:
1. Remover classe duplicate de jobs.py
2. Validar compilação
3. Rodar smoke test

---

## Passo 1: Verificar Estado Atual

### backend/app/services/jobs.py

**Procurar por**: Linha onde SQLiteSessionStore inicia (deve estar perto da linha 27)

```bash
cd c:\git\music-analyzer
grep -n "class SQLiteSessionStore" backend/app/services/jobs.py
```

**Resultado esperado**:
```
27:class SQLiteSessionStore:
```

**Verificar se já foi importado**:
```bash
grep -n "from app.repositories.session_store import" backend/app/services/jobs.py
```

**Resultado esperado**:
```
20:from app.repositories.session_store import SQLiteSessionStore
```

---

## Passo 2: Entender Estrutura Atual

### Ler início de jobs.py

```bash
head -100 backend/app/services/jobs.py
```

Deve mostrar:
- Lines 1-19: imports normais
- Line 20: import do SQLiteSessionStore do novo arquivo
- Lines 21-26: outras classes ou lógica
- Lines 27-660: SQLiteSessionStore class (DUPLICADA - REMOVER ISSO)
- Lines 661+: JobService class (manter)

---

## Passo 3: Calcular Exatas Linhas para Remover

**Encontrar a class SQLiteSessionStore**:
```bash
grep -n "^class SQLiteSessionStore" backend/app/services/jobs.py
```

**Encontrar a próxima class após SQLiteSessionStore**:
```bash
sed -n '27,700p' backend/app/services/jobs.py | grep -n "^class " | head -2
```

Vai mostrar algo tipo:
```
1:class SQLiteSessionStore:
635:class JobService:
```

**Interpretação**: SQLiteSessionStore é linha 27, JobService é linha 27+634 = 661

**Então remover**: Linhas 27 até 660 (inclusive)

---

## Passo 4: Backup (Segurança Primeiro)

```bash
# Fazer backup da versão atual
copy backend\app\services\jobs.py backend\app\services\jobs.py.backup

# Ou em PowerShell
Copy-Item backend/app/services/jobs.py backend/app/services/jobs.py.backup
```

---

## Passo 5: Remover Duplicate

### Opção A: Usar Editor (Mais Seguro)

1. Abrir `backend/app/services/jobs.py` no VS Code
2. Ir para Linha 27 (Ctrl+G)
3. Selecionar da linha 27 até linha 660 (segure Shift, clique na linha 660)
4. Deletar (Backspace ou Delete)
5. Salvar (Ctrl+S)

### Opção B: Usar Script Python

```python
# Remover linhas 27-660
with open('backend/app/services/jobs.py', 'r') as f:
    lines = f.readlines()

# Keep lines 1-26 (index 0-25) e 661+ (index 660+)
new_lines = lines[:26] + lines[660:]

with open('backend/app/services/jobs.py', 'w') as f:
    f.writelines(new_lines)

print(f"Removed lines 27-660 from jobs.py")
```

### Opção C: Usar PowerShell

```powershell
$content = Get-Content -Path "backend/app/services/jobs.py"
$newContent = $content[0..25] + $content[660..($content.Count-1)]
$newContent | Set-Content -Path "backend/app/services/jobs.py"
Write-Host "Removed lines 27-660"
```

---

## Passo 6: Validar Resultado

### Verificar que duplicata foi removida

```bash
grep -n "class SQLiteSessionStore" backend/app/services/jobs.py
```

**Resultado esperado**: Sem output (nenhuma match)

### Verificar que JobService ainda existe

```bash
grep -n "^class JobService" backend/app/services/jobs.py
```

**Resultado esperado**:
```
27:class JobService:
```

(linha agora é 27, antes era ~661)

### Verificar imports ainda existe

```bash
grep -n "from app.repositories.session_store import" backend/app/services/jobs.py
```

**Resultado esperado**:
```
20:from app.repositories.session_store import SQLiteSessionStore
```

---

## Passo 7: Compilar Backend

```bash
cd c:\git\music-analyzer\backend
python -m compileall app/
```

**Resultado esperado**:
```
Compiling app/__init__.py ...
Compiling app/main.py ...
Compiling app/models.py ...
Compiling app/repositories/__init__.py ...
Compiling app/repositories/session_store.py ...
Compiling app/services/jobs.py ...
...
[lista de arquivos sem ERRORS]
```

**Se houver erro tipo "SyntaxError"**: voltar para Passo 5, verificar se deletou linhas corretas.

---

## Passo 8: Rodar Smoke Test

```bash
cd c:\git\music-analyzer\backend

# Teste 1: Importações funcionam
python -c "from app.services.jobs import JobService; print('✅ Imports OK')"

# Teste 2: SessionRepository é acessível
python -c "from app.repositories.session_store import SQLiteSessionStore; print('✅ Repository OK')"

# Teste 3: JobService pode ser instanciado
python -c "
from app.services.jobs import JobService
from app.settings import settings
import os

# Criar DB temp para teste
test_db = 'test_smoke.db'
js = JobService(test_db)
code = js.create_session()
print(f'✅ Session created: {code}')

# Listar sessões
sessions = js.list_sessions()
print(f'✅ Sessions listed: {len(sessions)} found')

# Limpar DB temp
if os.path.exists(test_db):
    os.remove(test_db)
    print('✅ Cleanup done')
"
```

**Resultado esperado**:
```
✅ Imports OK
✅ Repository OK
✅ Session created: MX-XXXX
✅ Sessions listed: 1 found
✅ Cleanup done
```

---

## Passo 9: Validar Nenhuma Regressão

### Teste com a aplicação completa

```bash
# Se tiver docker-compose setup
docker-compose up -d
# Aguardar ~10 segundos
curl http://localhost:8000/api/sessions
# Deve retornar lista de sessões existentes (array)
# Exemplo: {"items": [], "total": 0, "page": 1, "page_size": 8}

# Se tiver app rodando localmente
python -m uvicorn app.main:app --reload
# Em outro terminal:
curl http://localhost:8000/api/sessions
```

---

## Passo 10: Git Commit

```bash
# Verificar mudanças
git status
# Deve mostrar: modified: backend/app/services/jobs.py

# Visualizar diff (confirmar que só removeu SQLiteSessionStore)
git diff backend/app/services/jobs.py

# Commitar
git add backend/app/services/jobs.py
git commit -m "Phase 0: Remove duplicate SQLiteSessionStore from jobs.py

- Classe SQLiteSessionStore já foi extraída para app/repositories/session_store.py
- Importação em jobs.py mantida (linha 20)
- Compilação validada: python -m compileall app/
- Smoke test passou: session create/list funcionam
- Nenhuma regressão"

# Ver resultado
git log --oneline -5
```

---

## Passo 11: Cleanup Final

```bash
# Remover backup se não precisar mais
rm backend/app/services/jobs.py.backup
# Ou em PowerShell:
Remove-Item backend/app/services/jobs.py.backup

# Remover test DB se criou
rm backend/test_smoke.db

# Confirmar workspace clean
git status
# Deve mostrar: On branch main, nothing to commit
```

---

## Checklist de Conclusão

- [ ] Encontrou linhas exatas da SQLiteSessionStore (deve ser ~27-660)
- [ ] Fez backup de jobs.py
- [ ] Removeu linhas 27-660
- [ ] Validou que SQLiteSessionStore não aparece mais
- [ ] Validou que JobService ainda existe
- [ ] Compilação passou (`python -m compileall app/` = 0 errors)
- [ ] Smoke test passou (session create/list)
- [ ] Git commit feito
- [ ] Backup removido

---

## Troubleshooting

### Erro: "SyntaxError: invalid syntax"

**Causa**: Provavelmente deletou demais ou de menos.

**Solução**:
```bash
# Restaurar backup
cp backend/app/services/jobs.py.backup backend/app/services/jobs.py

# Tentar novamente com exatas line numbers
# Verificar: grep -n para encontrar linhas exatas
```

### Erro: "ImportError: cannot import name 'SQLiteSessionStore'"

**Causa**: Deletou o import também (não deveria).

**Solução**:
```bash
# Verificar linha 20
sed -n '20p' backend/app/services/jobs.py

# Deve ter: from app.repositories.session_store import SQLiteSessionStore
# Se não tiver, adicionar manualmente

# Linha 20 deve ser:
# from app.repositories.session_store import SQLiteSessionStore
```

### Erro: "Module not found: app.repositories"

**Causa**: Falta arquivo `backend/app/repositories/__init__.py`

**Solução**:
```bash
# Criar o arquivo
touch backend/app/repositories/__init__.py
```

---

## Pós-Phase 0

Quando Phase 0 estiver 100% completo:
1. ✅ jobs.py limpo
2. ✅ Compilação OK
3. ✅ Smoke test OK

**Próximo**: Iniciar Phase 1 (ORM Setup)

Seguir: `docs/PHASE_1_ORM_SETUP.md`

---

**Duração esperada**: 30 minutos  
**Dificuldade**: Baixa (apenas remoção de código)  
**Risco**: Baixo (backup e smoke test protegem)

