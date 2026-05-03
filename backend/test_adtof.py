import os
import sys
import time

try:
    from adtof_pytorch import transcribe_to_midi
    print("Sucesso: adtof_pytorch importado corretamente.")
except ImportError as e:
    print(f"Erro ao importar adtof_pytorch: {e}")
    sys.exit(1)

# Caminho de um arquivo de bateria real do projeto
input_audio = r"c:\git\music-analyzer\storage\stems\19fd5045-3ed7-4bd0-9c16-51c49e196b56\drums.mp3"
output_midi = r"c:\git\music-analyzer\storage\exports\test_drum_transcription.mid"

if not os.path.exists(input_audio):
    print(f"Erro: Arquivo de áudio não encontrado em {input_audio}")
    sys.exit(1)

os.makedirs(os.path.dirname(output_midi), exist_ok=True)

print(f"Iniciando transcrição de: {input_audio}...")
start_time = time.time()

try:
    # Transcrever
    transcribe_to_midi(input_audio, output_midi)
    
    end_time = time.time()
    print(f"Transcrição concluída com sucesso em {end_time - start_time:.2f} segundos!")
    print(f"Arquivo gerado: {output_midi}")
    
except Exception as e:
    print(f"Ocorreu um erro durante a transcrição: {e}")
