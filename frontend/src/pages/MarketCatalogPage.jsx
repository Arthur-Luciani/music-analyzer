import { useDialog } from "../context/DialogContext";

function formatCatalogDate(dateValue) {
  if (!dateValue) {
    return "--";
  }

  const parsed = new Date(dateValue);
  if (Number.isNaN(parsed.getTime())) {
    return "--";
  }

  return parsed.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function sourceLabel(source) {
  return source === "user_created" ? "Criado pelo usuário" : "Catálogo importado";
}

function ArtistsView({
  artists,
  artistTotal,
  artistPage,
  totalArtistPages,
  artistQuery,
  artistsLoading,
  artistsError,
  onArtistQueryChange,
  onApplyArtistQuery,
  onClearArtistQuery,
  onRetryArtists,
  onPrevArtistPage,
  onNextArtistPage,
  onSelectArtist,
  onRenameArtist,
  onDeleteArtist,
  actionLoading,
}) {
  const { prompt } = useDialog();

  return (
    <section className="card animate-up" style={{ marginTop: 12 }}>
      <form
        className="search-filter"
        onSubmit={(event) => {
          event.preventDefault();
          onApplyArtistQuery();
        }}
      >
        <input
          type="text"
          value={artistQuery}
          placeholder="Buscar por nome do artista/banda"
          aria-label="buscar artista"
          onChange={(event) => onArtistQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") onClearArtistQuery();
          }}
        />
        <button className="btn btn-subtle" type="submit" disabled={artistsLoading}>
          Aplicar filtros
        </button>
        <button className="btn btn-subtle" type="button" onClick={onClearArtistQuery} disabled={artistsLoading}>
          Limpar
        </button>
      </form>

      {artistsError && (
        <div className="library-alert-row">
          <p className="error-banner" style={{ marginTop: 10, marginBottom: 0 }}>
            {artistsError}
          </p>
          <button className="btn btn-subtle" type="button" onClick={onRetryArtists} disabled={artistsLoading}>
            Tentar novamente
          </button>
        </div>
      )}

      {artistsLoading && <p className="inline-note">Carregando artistas...</p>}

      {!artistsLoading && artists.length === 0 && (
        <section className="card empty-state" style={{ marginTop: 12 }}>
          <h3>Nenhum artista encontrado</h3>
          <p>Ajuste a busca ou verifique se o catálogo de MIDI de mercado já foi importado.</p>
          <button className="btn btn-subtle" type="button" onClick={onRetryArtists}>
            Recarregar
          </button>
        </section>
      )}

      {!artistsLoading && artists.length > 0 && (
        <>
          <table className="library-table" aria-label="artistas do catálogo" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Músicas</th>
                <th>Origem</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {artists.map((artist) => {
                const rowIsBusy = actionLoading.includes(`artist:${artist.id}`);
                return (
                  <tr key={artist.id}>
                    <td>{artist.name}</td>
                    <td>{artist.track_count}</td>
                    <td>{sourceLabel(artist.source)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          className="btn btn-subtle"
                          type="button"
                          onClick={() => onSelectArtist(artist.id)}
                          disabled={rowIsBusy}
                        >
                          Ver músicas
                        </button>
                        <button
                          className="btn btn-subtle"
                          type="button"
                          onClick={async () => {
                            const newName = await prompt("Novo nome do artista:", artist.name, {
                              title: "Renomear artista",
                            });
                            if (newName && newName !== artist.name) {
                              onRenameArtist(artist.id, newName);
                            }
                          }}
                          disabled={rowIsBusy}
                        >
                          Renomear
                        </button>
                        <button
                          className="btn btn-danger"
                          type="button"
                          onClick={() => onDeleteArtist(artist.id, artist.name)}
                          disabled={rowIsBusy}
                        >
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="library-pagination">
            <p className="inline-note" style={{ marginTop: 0 }}>
              Página {artistPage} de {totalArtistPages} | {artistTotal} artistas
            </p>
            <div className="table-actions">
              <button className="btn btn-subtle" type="button" onClick={onPrevArtistPage} disabled={artistPage <= 1 || artistsLoading}>
                Anterior
              </button>
              <button
                className="btn btn-subtle"
                type="button"
                onClick={onNextArtistPage}
                disabled={artistPage >= totalArtistPages || artistsLoading}
              >
                Próxima
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function ArtistDetailView({
  artistDetail,
  artistDetailLoading,
  artistDetailError,
  tracks,
  trackTotal,
  trackPage,
  totalTrackPages,
  tracksLoading,
  tracksError,
  onRetryTracks,
  onPrevTrackPage,
  onNextTrackPage,
  onSelectTrack,
  onRenameTrack,
  onDeleteTrack,
  onRenameArtist,
  actionLoading,
  onBackToArtists,
}) {
  const { prompt } = useDialog();

  if (artistDetailLoading && !artistDetail) {
    return (
      <section className="card animate-up" style={{ marginTop: 12 }}>
        <p className="inline-note">Carregando artista...</p>
      </section>
    );
  }

  if (artistDetailError && !artistDetail) {
    return (
      <section className="card animate-up" style={{ marginTop: 12 }}>
        <p className="error-banner">{artistDetailError}</p>
      </section>
    );
  }

  if (!artistDetail) {
    return null;
  }

  return (
    <section className="card animate-up" style={{ marginTop: 12 }}>
      <div className="page-title-row">
        <div>
          <button className="btn btn-subtle" type="button" onClick={onBackToArtists}>
            ← Voltar aos artistas
          </button>
        </div>
      </div>

      <div className="page-title-row" style={{ marginTop: 12 }}>
        <h2 style={{ margin: 0 }}>{artistDetail.name}</h2>
        <button
          className="btn btn-subtle"
          type="button"
          onClick={async () => {
            const newName = await prompt("Novo nome do artista:", artistDetail.name, { title: "Renomear artista" });
            if (newName && newName !== artistDetail.name) {
              onRenameArtist(artistDetail.id, newName);
            }
          }}
        >
          Renomear artista
        </button>
      </div>

      {tracksError && (
        <div className="library-alert-row">
          <p className="error-banner" style={{ marginTop: 10, marginBottom: 0 }}>
            {tracksError}
          </p>
          <button className="btn btn-subtle" type="button" onClick={onRetryTracks} disabled={tracksLoading}>
            Tentar novamente
          </button>
        </div>
      )}

      {tracksLoading && <p className="inline-note">Carregando músicas...</p>}

      {!tracksLoading && tracks.length === 0 && (
        <section className="card empty-state" style={{ marginTop: 12 }}>
          <h3>Nenhuma música cadastrada para este artista</h3>
        </section>
      )}

      {!tracksLoading && tracks.length > 0 && (
        <>
          <table className="library-table" aria-label="musicas do artista" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Título</th>
                <th>Arquivos MIDI</th>
                <th>Origem</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((track) => {
                const rowIsBusy = actionLoading.includes(`track:${track.id}`);
                return (
                  <tr key={track.id}>
                    <td>{track.title}</td>
                    <td>{track.midi_file_count}</td>
                    <td>{sourceLabel(track.source)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          className="btn btn-subtle"
                          type="button"
                          onClick={() => onSelectTrack(track.id)}
                          disabled={rowIsBusy}
                        >
                          Ver arquivos
                        </button>
                        <button
                          className="btn btn-subtle"
                          type="button"
                          onClick={async () => {
                            const newTitle = await prompt("Novo título da música:", track.title, {
                              title: "Renomear música",
                            });
                            if (newTitle && newTitle !== track.title) {
                              onRenameTrack(track.id, { title: newTitle });
                            }
                          }}
                          disabled={rowIsBusy}
                        >
                          Renomear
                        </button>
                        <button
                          className="btn btn-danger"
                          type="button"
                          onClick={() => onDeleteTrack(track.id, track.title)}
                          disabled={rowIsBusy}
                        >
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="library-pagination">
            <p className="inline-note" style={{ marginTop: 0 }}>
              Página {trackPage} de {totalTrackPages} | {trackTotal} músicas
            </p>
            <div className="table-actions">
              <button className="btn btn-subtle" type="button" onClick={onPrevTrackPage} disabled={trackPage <= 1 || tracksLoading}>
                Anterior
              </button>
              <button
                className="btn btn-subtle"
                type="button"
                onClick={onNextTrackPage}
                disabled={trackPage >= totalTrackPages || tracksLoading}
              >
                Próxima
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function TrackDetailView({
  trackDetail,
  trackDetailLoading,
  trackDetailError,
  onRenameTrack,
  onDeleteTrack,
  onDeleteMidiFile,
  actionLoading,
  onBackToArtistDetail,
  onOpenSession,
  onCreateSessionForTrack,
}) {
  const { prompt } = useDialog();

  if (trackDetailLoading && !trackDetail) {
    return (
      <section className="card animate-up" style={{ marginTop: 12 }}>
        <p className="inline-note">Carregando música...</p>
      </section>
    );
  }

  if (trackDetailError && !trackDetail) {
    return (
      <section className="card animate-up" style={{ marginTop: 12 }}>
        <p className="error-banner">{trackDetailError}</p>
      </section>
    );
  }

  if (!trackDetail) {
    return null;
  }

  return (
    <section className="card animate-up" style={{ marginTop: 12 }}>
      <div className="page-title-row">
        <div>
          <button className="btn btn-subtle" type="button" onClick={onBackToArtistDetail}>
            ← Voltar às músicas
          </button>
        </div>
      </div>

      <div className="page-title-row" style={{ marginTop: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>{trackDetail.title}</h2>
          <p className="inline-note" style={{ marginTop: 4 }}>
            {trackDetail.artist_name}
          </p>
        </div>
        <div className="table-actions">
          <button
            className="btn btn-subtle"
            type="button"
            onClick={async () => {
              const newTitle = await prompt("Novo título da música:", trackDetail.title, { title: "Renomear música" });
              if (newTitle && newTitle !== trackDetail.title) {
                onRenameTrack(trackDetail.id, { title: newTitle });
              }
            }}
          >
            Renomear música
          </button>
          <button className="btn btn-danger" type="button" onClick={() => onDeleteTrack(trackDetail.id, trackDetail.title)}>
            Excluir música
          </button>
        </div>
      </div>

      {trackDetail.midi_files.length === 0 && (
        <section className="card empty-state" style={{ marginTop: 12 }}>
          <h3>Nenhum arquivo MIDI candidato para esta música</h3>
        </section>
      )}

      {trackDetail.midi_files.length > 0 && (
        <table className="library-table" aria-label="arquivos midi da musica" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Caminho</th>
              <th>Indexado em</th>
              <th>Sessão vinculada</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {trackDetail.midi_files.map((file) => {
              const rowIsBusy = actionLoading.includes(`file:${file.id}`);
              return (
                <tr key={file.id}>
                  <td>{file.relative_path}</td>
                  <td>{formatCatalogDate(file.indexed_at)}</td>
                  <td>
                    {file.linked_sessions.length === 0 ? (
                      <button className="btn btn-subtle" type="button" onClick={onCreateSessionForTrack}>
                        Criar sessão
                      </button>
                    ) : (
                      <div className="table-actions">
                        {file.linked_sessions.map((linked) => (
                          <button
                            key={linked.session_id}
                            className="btn btn-subtle"
                            type="button"
                            title={`${linked.session_code} — ${linked.state}`}
                            onClick={() => onOpenSession(linked.session_id)}
                          >
                            {linked.session_code}
                          </button>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="table-actions">
                      <button
                        className="btn btn-danger"
                        type="button"
                        onClick={() => onDeleteMidiFile(file.id, file.relative_path)}
                        disabled={rowIsBusy}
                      >
                        Excluir
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default function MarketCatalogPage(props) {
  const { view, actionMessage } = props;

  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>Catálogo de Mercado</h1>
        </div>
        <span className="state ready">Bandas, músicas e MIDI</span>
      </div>

      {actionMessage && <p className="inline-note">{actionMessage}</p>}

      {view === "artists" && <ArtistsView {...props} />}
      {view === "artistDetail" && <ArtistDetailView {...props} />}
      {view === "trackDetail" && <TrackDetailView {...props} />}
    </>
  );
}
