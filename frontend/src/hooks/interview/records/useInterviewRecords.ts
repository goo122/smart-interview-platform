import { useInfiniteQuery } from "@tanstack/react-query";
import { interviewService } from "@/services/interviewService";
import { useAppSelector } from "@/store/hooks";
import type { UserRespDTO } from "@/types/auth";

type InterviewRecordUserIdentity =
  | Pick<UserRespDTO, "id" | "username">
  | null
  | undefined;

type UseInterviewRecordsOptions = {
  enabled?: boolean;
};

const PAGE_SIZE = 20;

const getInterviewRecordUserKey = (user: InterviewRecordUserIdentity) => {
  if (!user) return "anonymous";
  if (typeof user.id === "number" && Number.isFinite(user.id) && user.id > 0) {
    return `id:${user.id}`;
  }
  if (user.username) return `username:${user.username}`;
  return "anonymous";
};

export function useInterviewRecords(options: UseInterviewRecordsOptions = {}) {
  const { isAuthenticated, currentUser, authEpoch } = useAppSelector(
    (state) => state.user,
  );
  const enabled = (options.enabled ?? true) && isAuthenticated;
  const userKey = getInterviewRecordUserKey(currentUser);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    refetch,
  } = useInfiniteQuery({
    queryKey: ["interview-records", userKey, authEpoch],
    queryFn: async ({ pageParam = 1 }) =>
      interviewService.pageInterviewRecords({
        pageNum: pageParam,
        pageSize: PAGE_SIZE,
      }),
    getNextPageParam: (lastPage) => {
      if (!lastPage || !Array.isArray(lastPage.records)) return undefined;
      if (lastPage.records.length < PAGE_SIZE) return undefined;
      if (lastPage.pages && lastPage.current >= lastPage.pages) {
        return undefined;
      }
      return lastPage.current + 1;
    },
    initialPageParam: 1,
    enabled,
  });

  return {
    interviewRecords: data?.pages.flatMap((page) => page.records) || [],
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    refetch,
  };
}
