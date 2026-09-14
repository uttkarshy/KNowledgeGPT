import type { Element, Root, RootContent } from "hast";

/** Transform parsed text only; never split raw Markdown or link/code syntax. */
export function rehypeCitations({ count }: { count: number }) {
  return (tree: Root) => {
    function visit(parent: Root | Element) {
      if (parent.type === "element" && ["a", "code", "pre"].includes(parent.tagName)) return;
      parent.children = parent.children.flatMap((child): RootContent[] => {
        if (child.type === "element") visit(child);
        if (child.type !== "text") return [child];
        const output: RootContent[] = [];
        let start = 0;
        for (const match of child.value.matchAll(/\[(\d+)\]/g)) {
          const index = Number(match[1]);
          if (index < 1 || index > count) continue;
          const offset = match.index!;
          if (offset > start) output.push({ type: "text", value: child.value.slice(start, offset) });
          output.push({ type: "element", tagName: "span", properties: { "data-citation": index }, children: [] });
          start = offset + match[0].length;
        }
        if (start < child.value.length) output.push({ type: "text", value: child.value.slice(start) });
        return output;
      }) as typeof parent.children;
    }
    visit(tree);
  };
}
