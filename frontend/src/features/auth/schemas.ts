import { z } from "zod";

export const loginSchema = z.object({
  account: z.string().trim().min(1, "请输入邮箱或用户名"),
  password: z.string().min(1, "请输入密码"),
});

export const registerSchema = z
  .object({
    username: z.string().trim().min(3, "用户名至少需要 3 个字符").max(64),
    email: z.string().trim().email("请输入有效邮箱").max(320),
    password: z.string().min(8, "密码至少需要 8 个字符").max(128),
    confirmPassword: z.string().min(1, "请再次输入密码"),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "两次输入的密码不一致",
  });

export type LoginFormValues = z.infer<typeof loginSchema>;
export type RegisterFormValues = z.infer<typeof registerSchema>;
