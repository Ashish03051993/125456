import { useEffect } from "react";

// Sets `document.title` on mount and restores the default when the component
// unmounts. Keeps browser tabs, history entries and bookmarks contextual — big
// SEO + accessibility win without dragging in `react-helmet`.
const DEFAULT_TITLE = "ContentOS AI — Turn any topic into a polished video";

export default function usePageTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} · ContentOS AI` : DEFAULT_TITLE;
    return () => { document.title = prev; };
  }, [title]);
}
