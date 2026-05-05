
import numpy as np
import math
from collections import Counter

class GrooveSimilarity:
    @staticmethod
    def weighted_hamming_distance(bitsA, bitsB):
        """Hamming distance weighted by velocity (if provided)."""
        # Aqui bitsA e bitsB são strings de '0's e '1's
        a = np.array([int(c) for c in bitsA])
        b = np.array([int(c) for c in bitsB])
        x = a - b
        return math.sqrt(np.dot(x, x.T))

    @staticmethod
    def fuzzy_hamming_distance(bitsA, bitsB, grid_size=16):
        """
        Calcula a distância de Hamming com tolerância de 1 slot para frente/trás.
        Inspirado no GrooveToolbox.
        """
        a = [int(c) for c in bitsA]
        b = [int(c) for c in bitsB]
        
        distance = 0
        matched_b = [False] * grid_size
        
        # Primeiro, casar notas na mesma posição
        for i in range(grid_size):
            if a[i] == 1 and b[i] == 1:
                matched_b[i] = True
            elif a[i] == 1:
                # Procurar vizinhos
                found = False
                for offset in [-1, 1]:
                    neighbor = (i + offset) % grid_size
                    if b[neighbor] == 1 and not matched_b[neighbor]:
                        distance += 0.5 # Penalidade menor para nota deslocada
                        matched_b[neighbor] = True
                        found = True
                        break
                if not found:
                    distance += 1.0 # Penalidade cheia para nota faltando
        
        # Contar notas em b que não foram casadas
        for i in range(grid_size):
            if b[i] == 1 and not matched_b[i]:
                distance += 1.0
                
        return distance

class RhythmMetrics:
    @staticmethod
    def calculate_syncopation(bits, grid_size=16):
        """
        Longeuet-Higgins & Lee (1984) syncopation measure.
        """
        if grid_size == 16:
            profile = [5, 1, 2, 1, 3, 1, 2, 1, 4, 1, 2, 1, 3, 1, 2, 1]
        elif grid_size == 12:
            profile = [4, 1, 1, 3, 1, 1, 3, 1, 1, 3, 1, 1] # Simplificado para ternário
        else:
            return 0
            
        sync = 0
        n = len(bits)
        for i in range(n):
            if bits[i] == '1':
                # Check next positions
                for next_off in [1, 2]:
                    next_idx = (i + next_off) % n
                    if bits[next_idx] == '0' and profile[next_idx] > profile[i]:
                        sync += (profile[next_idx] - profile[i])
        return sync / 30.0 # Normalizado aproximado
