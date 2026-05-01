import { useEffect, useRef } from "react";

type Props = {
  content: string;
  isStreaming?: boolean;
};

export default function AnswerStream({ content, isStreaming }: Props) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (el.current) el.current.scrollTop = el.current.scrollHeight;
  }, [content]);

  return (
    <div
      ref={el}
      className="p-4 bg-gray-50 rounded-lg min-h-[120px] max-h-[400px] overflow-y-auto whitespace-pre-wrap text-gray-800"
    >
      {content || (isStreaming ? "..." : "Ask a question to see the answer here.")}
      {isStreaming && <span className="animate-pulse">▌</span>}
    </div>
  );
}
