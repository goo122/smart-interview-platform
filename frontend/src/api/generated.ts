// AUTO-GENERATED from backend FastAPI OpenAPI. Do not edit manually.

export interface components {
  schemas: {
    LoginRequest: {
      "account": string;
      "password": string;
    };
    MessageResponse: {
      "message": string;
    };
    RefreshRequest: {
      "refresh_token": string;
    };
    RegisterRequest: {
      "username": string;
      "email": string;
      "password": string;
    };
    TokenResponse: {
      "access_token": string;
      "refresh_token": string;
      "token_type": "bearer";
      "expires_in": number;
    };
    UserResponse: {
      "id": string;
      "username": string;
      "email": string;
      "is_active": boolean;
      "created_at": string;
      "updated_at": string;
    };
  };
}

export type LoginRequest = components["schemas"]["LoginRequest"];
export type MessageResponse = components["schemas"]["MessageResponse"];
export type RefreshRequest = components["schemas"]["RefreshRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserResponse = components["schemas"]["UserResponse"];
