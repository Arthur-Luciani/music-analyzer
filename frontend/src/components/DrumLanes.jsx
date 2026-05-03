import React, { useMemo } from 'react';
import './DrumLanes.css';

const LANES = [
  { id: 'kick', label: 'Bumbo' },
  { id: 'snare', label: 'Caixa' },
  { id: 'hihat', label: 'Chimbal' },
  { id: 'tom', label: 'Tons' },
  { id: 'cymbal', label: 'Pratos' },
  { id: 'other', label: 'Outros' },
];

const PIXELS_PER_SECOND = 60; // Compact Workspace Zoom
const PLAYHEAD_OFFSET = 100; // Left offset to keep playhead in view

const DrumLanes = ({ analysis, currentTime, duration, hideLabels = false }) => {
  if (!analysis || !analysis.hits) return null;

  const hitsByLane = useMemo(() => {
    const grouped = {
      kick: [], snare: [], hihat: [], tom: [], cymbal: [], other: []
    };
    analysis.hits.forEach(hit => {
      const laneId = grouped[hit.type] ? hit.type : 'other';
      grouped[laneId].push(hit);
    });
    return grouped;
  }, [analysis]);

  const totalWidth = duration * PIXELS_PER_SECOND;
  const playheadPos = currentTime * PIXELS_PER_SECOND;

  return (
    <div className="drum-lanes-root" style={{ border: hideLabels ? 'none' : undefined, background: hideLabels ? 'transparent' : undefined, marginTop: hideLabels ? 0 : undefined }}>
      <div className="drum-lanes-viewport" style={{ background: hideLabels ? 'transparent' : undefined }}>
        {/* Fixed labels on the left */}
        {!hideLabels && (
          <div className="drum-lane-labels">
            {LANES.map(lane => (
              <div key={lane.id} className="drum-lane-label">
                {lane.label}
              </div>
            ))}
          </div>
        )}

        {/* Scrollable content moved by transform for better performance in Workspace */}
        <div className="drum-lanes-content">
          <div 
            className="hits-wrapper" 
            style={{ 
              width: `${totalWidth}px`,
              transform: `translateX(-${Math.max(0, playheadPos - PLAYHEAD_OFFSET)}px)`
            }}
          >
            {/* Playhead line */}
            <div 
              className="drum-playhead" 
              style={{ left: `${playheadPos}px` }}
            />

            {/* Hit Rows */}
            {LANES.map((lane) => (
              <div key={`row-${lane.id}`} className="grid-lane-row">
                {hitsByLane[lane.id].map((hit, hitIdx) => {
                  const left = hit.time * PIXELS_PER_SECOND;
                  return (
                    <div 
                      key={`${lane.id}-${hitIdx}`}
                      className={`drum-hit ${lane.id}`}
                      style={{ left: `${left}px` }}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DrumLanes;
