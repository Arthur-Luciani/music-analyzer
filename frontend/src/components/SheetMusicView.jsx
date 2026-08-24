import { useEffect, useRef, useState } from "react";
import { OpenSheetMusicDisplay } from "opensheetmusicdisplay";
import { getDrumMusicXmlUrl } from "../api";
import "./SheetMusicView.css";

const MAX_CURSOR_STEPS = 20000; // guarda de segurança contra loop infinito

export default function SheetMusicView({ sessionId, bpm, currentTime, onSeek }) {
  const containerRef = useRef(null);
  const osmdRef = useRef(null);
  const stepsRef = useRef([]); // [{ seconds, x }] por posição do cursor, em ordem
  const cursorIndexRef = useRef(0);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!sessionId || !containerRef.current) return undefined;
    let cancelled = false;
    setStatus("loading");
    setErrorMessage("");

    async function load() {
      try {
        const response = await fetch(getDrumMusicXmlUrl(sessionId));
        if (!response.ok) {
          throw new Error(`Falha ao carregar partitura (HTTP ${response.status})`);
        }
        const xmlText = await response.text();
        if (cancelled) return;

        containerRef.current.innerHTML = "";
        const osmd = new OpenSheetMusicDisplay(containerRef.current, {
          autoResize: true,
          drawTitle: false,
          followCursor: true,
          backend: "svg",
        });

        await osmd.load(xmlText);
        if (cancelled) return;
        osmd.render();

        buildStepLookup(osmd, bpm);
        osmd.cursor.reset();
        osmd.cursor.show();
        cursorIndexRef.current = 0;
        osmdRef.current = osmd;

        setStatus("ready");
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(err.message || "Falha ao carregar partitura");
          setStatus("error");
        }
      }
    }

    load();

    return () => {
      cancelled = true;
      osmdRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, bpm]);

  function buildStepLookup(osmd, bpmValue) {
    const secondsPerQuarter = 60 / (bpmValue > 0 ? bpmValue : 120);
    const cursor = osmd.cursor;
    const containerRect = containerRef.current.getBoundingClientRect();

    cursor.hide(); // evita o cursor "varrendo" a tela inteira durante essa varredura
    cursor.reset();

    const steps = [];
    let guard = 0;
    while (!cursor.iterator.EndReached && guard < MAX_CURSOR_STEPS) {
      const wholeNotes = cursor.iterator.currentTimeStamp.RealValue;
      const seconds = wholeNotes * 4 * secondsPerQuarter;
      const cursorRect = cursor.cursorElement?.getBoundingClientRect();
      const x = cursorRect ? cursorRect.left - containerRect.left : null;
      steps.push({ seconds, x });
      cursor.next();
      guard += 1;
    }

    stepsRef.current = steps;
    cursor.reset();
    cursor.show();
  }

  // Sincroniza a posição do cursor com o tempo de reprodução atual.
  useEffect(() => {
    const osmd = osmdRef.current;
    const steps = stepsRef.current;
    if (!osmd || status !== "ready" || steps.length === 0) return;

    let low = 0;
    let high = steps.length - 1;
    while (low < high) {
      const mid = (low + high) >> 1;
      if (steps[mid].seconds < currentTime) low = mid + 1;
      else high = mid;
    }
    const targetIndex = low;

    const cursor = osmd.cursor;
    let current = cursorIndexRef.current;
    while (current < targetIndex && !cursor.iterator.EndReached) {
      cursor.next();
      current += 1;
    }
    while (current > targetIndex && current > 0) {
      cursor.previous();
      current -= 1;
    }
    cursorIndexRef.current = current;
  }, [currentTime, status]);

  function handleContainerClick(event) {
    const steps = stepsRef.current;
    if (!osmdRef.current || steps.length === 0 || typeof onSeek !== "function") return;

    const containerRect = containerRef.current.getBoundingClientRect();
    const clickX = event.clientX - containerRect.left;

    let closestIndex = 0;
    let closestDistance = Infinity;
    steps.forEach((step, index) => {
      if (step.x === null) return;
      const distance = Math.abs(step.x - clickX);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestIndex = index;
      }
    });

    onSeek(steps[closestIndex].seconds);
  }

  return (
    <div className="sheet-music-view">
      {status === "loading" && <div className="sheet-music-status">Carregando partitura...</div>}
      {status === "error" && <div className="sheet-music-status error">{errorMessage}</div>}
      <div
        className="sheet-music-container"
        ref={containerRef}
        onClick={handleContainerClick}
      />
    </div>
  );
}
