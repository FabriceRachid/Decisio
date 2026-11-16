import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="text-xl font-display font-bold text-foreground mt-0 mb-3 pb-2 border-b border-border/40">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-lg font-display font-bold text-foreground mt-5 mb-2 pb-1.5 border-b border-border/30">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-base font-display font-semibold text-foreground mt-4 mb-2">
            {children}
          </h3>
        ),
        p: ({ children }) => (
          <p className="text-sm leading-relaxed text-foreground/90 mb-3 last:mb-0">
            {children}
          </p>
        ),
        ul: ({ children }) => (
          <ul className="space-y-1.5 mb-3 ml-1">
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol className="space-y-1.5 mb-3 ml-1 list-decimal">
            {children}
          </ol>
        ),
        li: ({ children }) => (
          <li className="text-sm leading-relaxed text-foreground/90 flex items-start gap-2">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/50" />
            <span>{children}</span>
          </li>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-foreground">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-foreground/80">{children}</em>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return (
              <code className="block rounded-lg bg-muted/60 border border-border/30 px-4 py-3 text-xs font-mono text-foreground/80 overflow-x-auto my-3 whitespace-pre">
                {children}
              </code>
            );
          }
          return (
            <code className="rounded-md bg-muted/60 px-1.5 py-0.5 text-xs font-mono text-foreground/80">
              {children}
            </code>
          );
        },
        pre: ({ children }) => (
          <pre className="my-3">{children}</pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-3 border-primary/30 bg-primary/5 rounded-r-lg px-4 py-3 my-3 text-sm text-foreground/80">
            {children}
          </blockquote>
        ),
        hr: () => (
          <hr className="my-5 border-border/30" />
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-3 rounded-lg border border-border/40">
            <table className="w-full text-sm">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-muted/40 border-b border-border/30">{children}</thead>
        ),
        th: ({ children }) => (
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 border-b border-border/20 last:border-b-0">
            {children}
          </td>
        ),
      }}
    >
      {content}
    </Markdown>
  );
}
