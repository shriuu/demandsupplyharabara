import { createContext, useContext, useEffect } from "react";

/** The screen tells the chat panel which suggestion is in front of the person. */
export const ChatFocus = createContext<(id: string | null) => void>(() => undefined);

export function useChatFocus(id: string | null) {
  const set = useContext(ChatFocus);
  useEffect(() => {
    set(id);
    return () => set(null);
  }, [id, set]);
}
