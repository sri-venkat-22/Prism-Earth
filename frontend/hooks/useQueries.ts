// React Query mutation hooks for the two action endpoints: the deterministic
// Fetch API (SRS §13.9) and the natural-language Ask API (SRS §13.13).

import { useMutation } from "@tanstack/react-query";

import { postAsk, postFetch } from "@/services/api";
import type { AskRequest, AskResponse, FetchRequest, FetchResponse } from "@/types";

export function useFetchQuery() {
  return useMutation<FetchResponse, Error, FetchRequest>({
    mutationFn: (payload) => postFetch(payload),
  });
}

export function useAskQuery() {
  return useMutation<AskResponse, Error, AskRequest>({
    mutationFn: (payload) => postAsk(payload),
  });
}
