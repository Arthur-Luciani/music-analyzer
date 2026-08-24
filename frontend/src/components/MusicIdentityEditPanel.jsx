export default function MusicIdentityEditPanel({
  artistText,
  titleText,
  setTitleText,
  onArtistTextChange,
  selectedArtistId,
  suggestions,
  resolving,
  pickSuggestion,
  saving,
  error,
  onSave,
  onCancel,
}) {
  return (
    <div className="identity-edit-panel">
      <div className="field-grid">
        <label htmlFor="edit-identity-artist">Artista</label>
        <div className="input-row">
          <input
            id="edit-identity-artist"
            type="text"
            value={artistText}
            onChange={(event) => onArtistTextChange(event.target.value)}
            disabled={saving}
          />
          {selectedArtistId && <span className="compatibility-pill high">Vinculado ao catálogo</span>}
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

        <label htmlFor="edit-identity-title">Música</label>
        <div className="input-row">
          <input
            id="edit-identity-title"
            type="text"
            value={titleText}
            onChange={(event) => setTitleText(event.target.value)}
            disabled={saving}
          />
        </div>
      </div>

      {error && <p className="error-banner small">{error}</p>}

      <div className="input-row" style={{ marginTop: 10 }}>
        <button type="button" className="btn btn-subtle" onClick={onCancel} disabled={saving}>
          Cancelar
        </button>
        <button type="button" className="btn btn-accent" onClick={onSave} disabled={saving}>
          {saving ? "Salvando..." : "Salvar e rebuscar MIDI"}
        </button>
      </div>
    </div>
  );
}
