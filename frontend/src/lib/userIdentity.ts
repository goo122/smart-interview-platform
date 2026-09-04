export type UserIdentity = {
  id?: string | null;
  username?: string | null;
};

export const getScopedUserIdentity = (
  user: UserIdentity | null | undefined,
) => {
  const userId = user?.id?.trim();
  if (userId) return `id:${userId}`;

  const username = user?.username?.trim();
  if (username) return `username:${username}`;

  return "anonymous";
};
