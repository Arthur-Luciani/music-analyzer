export default function MusicIdentityStep({
  sessionCode,
  artistText,
  titleText,
  setTitleText,
  onArtistTextChange,
  selectedArtistId,
  suggestions,
  resolving,
  pickSuggestion,
  confirming,
  error,
  onConfirm,
  onBack,
}) {
  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>Confirmar artista e música</h1>
        </div>
        <span className="state processing">Passo 3 de 3</span>
      </div>

      <div className="main-grid" style={{ marginTop: 12 }}>
        <section className="card hero-card animate-up" style={{ animationDelay: "90ms" }}>
          <h2 style={{ marginTop: 10 }}>Sessão {sessionCode}</h2>
          <p className="inline-note">
            Corrija o artista e o título se a busca trouxe algo impreciso (nome de canal do YouTube,
            por exemplo) — isso melhora a chance de encontrarmos um MIDI de mercado equivalente pra
            essa música.
          </p>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (!confirming) onConfirm();
            }}
          >
            <div className="field-grid">
              <label htmlFor="identity-artist">Artista</label>
              <div className="input-row">
                <input
                  id="identity-artist"
                  type="text"
                  value={artistText}
                  onChange={(event) => onArtistTextChange(event.target.value)}
                  placeholder="Ex: Survivor"
                  disabled={confirming}
                />
                {selectedArtistId && (
                  <span className="compatibility-pill high">Vinculado ao catálogo</span>
                )}
              </div>

              {resolving && <p className="inline-note">Buscando sugestões...</p>}

              {suggestions.length > 0 && (
                <div className="identity-suggestions">
                  {suggestions.map((candidate) => (
                    <button
                      key={candidate.id}
                      type="button"
                      className="identity-suggestion-chip"
                      onClick={() => pickSuggestion(candidate)}
                    >
                      {candidate.name} · {Math.round(candidate.score)}%
                    </button>
                  ))}
                </div>
              )}

              <label htmlFor="identity-title">Música</label>
              <div className="input-row">
                <input
                  id="identity-title"
                  type="text"
                  value={titleText}
                  onChange={(event) => setTitleText(event.target.value)}
                  placeholder="Ex: Eye Of The Tiger"
                  disabled={confirming}
                />
              </div>
            </div>

            {error && <p className="error-banner">{error}</p>}

            <div className="input-row" style={{ marginTop: 16 }}>
              <button type="button" className="btn btn-subtle" onClick={onBack} disabled={confirming}>
                Voltar
              </button>
              <button type="submit" className="btn btn-accent" disabled={confirming}>
                {confirming ? "Confirmando..." : "Confirmar e iniciar processamento"}
              </button>
            </div>
          </form>
        </section>

        <aside className="stack">
          <section className="card animate-up" style={{ animationDelay: "170ms" }}>
            <h3>Por que isso importa</h3>
            <ul className="flow-checklist">
              <li>Nomes de canal do YouTube às vezes não batem com o nome real do artista.</li>
              <li>Confirmar aqui evita que a busca de MIDI de mercado erre por causa disso.</li>
              <li>Se você voltar agora, este rascunho é descartado.</li>
            </ul>
          </section>
        </aside>
      </div>
    </>
  );
}
