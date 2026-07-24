// Reliable cross-origin file downloader.
//
// The plain `<a download="name.mp4">` attribute is a browser HINT — modern
// browsers silently ignore it whenever they think the file could be inline
// (video/mp4 with no Content-Disposition, cross-origin edge cases, etc.),
// which is why users were seeing blank filenames in their downloads folder.
//
// This helper fetches the file as a blob and creates an object URL, so the
// download filename is enforced by the browser instead of being merely
// suggested. Falls back to a plain anchor click if the fetch itself fails.
import { toast } from "sonner";

/**
 * @param {string} url        Fully-resolved URL to the file.
 * @param {string} filename   Filename the user should see in their downloads.
 */
export async function downloadFile(url, filename) {
  if (!url) return;
  const safeName = (filename || "download").replace(/[/\\?%*:|"<>]/g, "_").slice(0, 200);
  let toastId;
  try {
    toastId = toast.loading(`Preparing ${safeName}…`);
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objUrl;
    a.download = safeName;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Revoke on next tick so the download has time to start.
    setTimeout(() => URL.revokeObjectURL(objUrl), 1500);
    toast.success(`Downloading ${safeName}`, { id: toastId });
  } catch (e) {
    // Fallback: open the URL in a new tab so the user at least gets the file.
    toast.error(`Couldn't force-download — opening in new tab.`, { id: toastId });
    try {
      const w = window.open(url, "_blank", "noopener");
      if (!w) window.location.href = url;
    } catch { window.location.href = url; }
  }
}
