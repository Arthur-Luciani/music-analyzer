import { useEffect } from "react";
import { useMarketCatalog } from "../hooks/useMarketCatalog";
import MarketCatalogPage from "../pages/MarketCatalogPage";
import { PAGES } from "../constants";

export default function MarketCatalogContainer({ setCurrentPage, onOpenWizardWithQuery }) {
  const catalog = useMarketCatalog();

  useEffect(() => {
    catalog.fetchArtists();
  }, [catalog.artistPage, catalog.appliedArtistQuery, catalog.fetchArtists]);

  useEffect(() => {
    if (catalog.view === "artistDetail" && catalog.selectedArtistId != null) {
      catalog.fetchTracks();
    }
  }, [catalog.view, catalog.selectedArtistId, catalog.trackPage, catalog.fetchTracks]);

  return (
    <MarketCatalogPage
      view={catalog.view}
      artists={catalog.artistPayload.items || []}
      artistTotal={catalog.artistPayload.total || 0}
      artistPage={catalog.artistPage}
      totalArtistPages={catalog.totalArtistPages}
      artistQuery={catalog.artistQuery}
      artistsLoading={catalog.artistsLoading}
      artistsError={catalog.artistsError}
      onArtistQueryChange={catalog.setArtistQuery}
      onApplyArtistQuery={() => {
        catalog.setArtistPage(1);
        catalog.setAppliedArtistQuery(catalog.artistQuery);
      }}
      onClearArtistQuery={() => {
        catalog.setArtistQuery("");
        catalog.setAppliedArtistQuery("");
        catalog.setArtistPage(1);
      }}
      onRetryArtists={catalog.fetchArtists}
      onPrevArtistPage={() => catalog.setArtistPage((p) => Math.max(1, p - 1))}
      onNextArtistPage={() => catalog.setArtistPage((p) => Math.min(catalog.totalArtistPages, p + 1))}
      onSelectArtist={catalog.fetchArtistDetail}
      onRenameArtist={catalog.handleRenameArtist}
      onDeleteArtist={catalog.handleDeleteArtist}
      artistDetail={catalog.artistDetail}
      artistDetailLoading={catalog.artistDetailLoading}
      artistDetailError={catalog.artistDetailError}
      tracks={catalog.trackPayload.items || []}
      trackTotal={catalog.trackPayload.total || 0}
      trackPage={catalog.trackPage}
      totalTrackPages={catalog.totalTrackPages}
      tracksLoading={catalog.tracksLoading}
      tracksError={catalog.tracksError}
      onRetryTracks={catalog.fetchTracks}
      onPrevTrackPage={() => catalog.setTrackPage((p) => Math.max(1, p - 1))}
      onNextTrackPage={() => catalog.setTrackPage((p) => Math.min(catalog.totalTrackPages, p + 1))}
      onSelectTrack={catalog.fetchTrackDetail}
      onRenameTrack={catalog.handleRenameTrack}
      onDeleteTrack={catalog.handleDeleteTrack}
      trackDetail={catalog.trackDetail}
      trackDetailLoading={catalog.trackDetailLoading}
      trackDetailError={catalog.trackDetailError}
      onDeleteMidiFile={catalog.handleDeleteMidiFile}
      onOpenSession={() => setCurrentPage(PAGES.library)}
      onCreateSessionForTrack={() => {
        if (!catalog.trackDetail) return;
        onOpenWizardWithQuery(`${catalog.trackDetail.title} ${catalog.trackDetail.artist_name}`);
      }}
      actionLoading={catalog.actionLoading}
      actionMessage={catalog.actionMessage}
      onBackToArtists={catalog.goBackToArtists}
      onBackToArtistDetail={catalog.goBackToArtistDetail}
    />
  );
}
