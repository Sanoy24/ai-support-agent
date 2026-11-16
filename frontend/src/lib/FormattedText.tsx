import { Fragment } from "react";

const BOLD = /\*\*(.+?)\*\*/g;

/**
 * Renders model text with **bold** spans as real bold text. Everything is
 * rendered as React text nodes, never as HTML, so replies can't inject
 * markup into the page.
 */
export function FormattedText({ text }: { text: string }) {
  const parts: (string | { bold: string })[] = [];
  let last = 0;
  for (const match of text.matchAll(BOLD)) {
    const index = match.index ?? 0;
    if (index > last) parts.push(text.slice(last, index));
    parts.push({ bold: match[1] ?? "" });
    last = index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));

  return (
    <>
      {parts.map((part, i) =>
        typeof part === "string" ? (
          <Fragment key={i}>{part}</Fragment>
        ) : (
          <strong key={i} className="font-semibold">
            {part.bold}
          </strong>
        ),
      )}
    </>
  );
}
