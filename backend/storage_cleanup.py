import os
import sqlite3
import shutil

# Configurações
DB_PATH = r"c:\git\music-analyzer\storage\sessions.db"
STORAGE_ROOT = r"c:\git\music-analyzer\storage"
SUBDIRS_TO_CLEAN = ["stems", "raw", "exports"]

def get_valid_session_ids():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions")
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return set(ids)
    except Exception as e:
        print(f"Erro ao acessar banco de dados: {e}")
        return set()

def cleanup():
    valid_ids = get_valid_session_ids()
    if not valid_ids:
        print("Nenhuma sessao valida encontrada ou erro no banco. Abortando.")
        return

    print(f"Sessoes validas encontradas: {len(valid_ids)}")
    total_deleted = 0
    total_freed_bytes = 0

    for sub in SUBDIRS_TO_CLEAN:
        dir_path = os.path.join(STORAGE_ROOT, sub)
        if not os.path.exists(dir_path):
            continue
            
        print(f"\nLimpando pasta: {sub}")
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            
            # Ignorar arquivos de controle (ex: .gitkeep)
            if item.startswith("."):
                continue
                
            # Se for um diretorio com nome de UUID
            if os.path.isdir(item_path):
                # Se o nome do diretorio nao for uma sessao valida
                if item not in valid_ids and item not in ["diag_cuda_check", "smoke_test_container"]:
                    size = get_dir_size(item_path)
                    print(f"  [ORFAO] Removendo: {item} ({size/1024/1024:.2f} MB)")
                    try:
                        shutil.rmtree(item_path)
                        total_deleted += 1
                        total_freed_bytes += size
                    except Exception as e:
                        print(f"    Erro ao remover {item}: {e}")
            
            # Se for um arquivo no raw que nao pertence a uma sessao (se seguir padrao UUID.ext)
            elif os.path.isfile(item_path) and sub == "raw":
                session_id = item.split(".")[0]
                if session_id not in valid_ids:
                    size = os.path.getsize(item_path)
                    print(f"  [ORFAO] Removendo arquivo: {item} ({size/1024/1024:.2f} MB)")
                    try:
                        os.remove(item_path)
                        total_deleted += 1
                        total_freed_bytes += size
                    except Exception as e:
                        print(f"    Erro ao remover arquivo {item}: {e}")

    print(f"\n--- Limpeza Concluida ---")
    print(f"Total de itens removidos: {total_deleted}")
    print(f"Espaço recuperado: {total_freed_bytes/1024/1024:.2f} MB")

def get_dir_size(path):
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    return total

if __name__ == "__main__":
    cleanup()
