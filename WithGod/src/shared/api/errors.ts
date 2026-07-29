import { AxiosError } from "axios";
import { ZodError } from "zod";

import { t } from "@/shared/lib/i18n";

// 에러 타입 정의
export type ApiErrorType =
  | "NETWORK_ERROR"
  | "TIMEOUT_ERROR"
  | "SERVER_ERROR"
  | "VALIDATION_ERROR"
  | "PARSE_ERROR"
  | "UNKNOWN_ERROR";

// 커스텀 API 에러 클래스
export class ApiError extends Error {
  type: ApiErrorType;
  statusCode?: number;
  originalError?: Error;

  constructor(
    type: ApiErrorType,
    message: string,
    statusCode?: number,
    originalError?: Error
  ) {
    super(message);
    this.name = "ApiError";
    this.type = type;
    this.statusCode = statusCode;
    this.originalError = originalError;
  }

  // 사용자에게 보여줄 메시지
  get userMessage(): string {
    switch (this.type) {
      case "NETWORK_ERROR":
        return t("errors.network");
      case "TIMEOUT_ERROR":
        return t("errors.timeout");
      case "SERVER_ERROR":
        return t("errors.server");
      case "VALIDATION_ERROR":
        return t("errors.validation");
      case "PARSE_ERROR":
        return t("errors.parse");
      default:
        return t("errors.unknown");
    }
  }

  // 재시도 가능 여부
  get isRetryable(): boolean {
    return (
      this.type === "NETWORK_ERROR" ||
      this.type === "TIMEOUT_ERROR" ||
      (this.type === "SERVER_ERROR" && this.statusCode !== undefined && this.statusCode >= 500)
    );
  }
}

// Axios 에러를 ApiError로 변환
export function parseAxiosError(error: AxiosError): ApiError {
  // 네트워크 에러 (인터넷 연결 없음)
  if (!error.response) {
    if (error.code === "ECONNABORTED" || error.message.includes("timeout")) {
      return new ApiError(
        "TIMEOUT_ERROR",
        "Request timeout",
        undefined,
        error
      );
    }
    return new ApiError(
      "NETWORK_ERROR",
      error.message || "Network error",
      undefined,
      error
    );
  }

  const status = error.response.status;

  // 4xx 클라이언트 에러
  if (status >= 400 && status < 500) {
    if (status === 422) {
      return new ApiError(
        "VALIDATION_ERROR",
        "Validation failed",
        status,
        error
      );
    }
    return new ApiError(
      "VALIDATION_ERROR",
      `Client error: ${status}`,
      status,
      error
    );
  }

  // 5xx 서버 에러
  if (status >= 500) {
    return new ApiError(
      "SERVER_ERROR",
      `Server error: ${status}`,
      status,
      error
    );
  }

  return new ApiError("UNKNOWN_ERROR", error.message, status, error);
}

// Zod 에러를 ApiError로 변환
export function parseZodError(error: ZodError): ApiError {
  const issues = error.issues.map((issue) => issue.message).join(", ");
  return new ApiError(
    "PARSE_ERROR",
    `Data validation failed: ${issues}`,
    undefined,
    error
  );
}

// 일반 에러를 ApiError로 변환
export function parseError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (error instanceof AxiosError) {
    return parseAxiosError(error);
  }

  if (error instanceof ZodError) {
    return parseZodError(error);
  }

  if (error instanceof Error) {
    return new ApiError("UNKNOWN_ERROR", error.message, undefined, error);
  }

  return new ApiError("UNKNOWN_ERROR", String(error));
}

// 에러 로깅 유틸리티
export function logError(error: ApiError, context?: string): void {
  if (__DEV__) {
    console.group(`[API Error]${context ? ` ${context}` : ""}`);
    console.log("Type:", error.type);
    console.log("Message:", error.message);
    console.log("User Message:", error.userMessage);
    console.log("Status Code:", error.statusCode);
    console.log("Retryable:", error.isRetryable);
    console.log("Stack:", error.stack);
    if (error.originalError) {
      console.log("Original Error:", error.originalError);
      if (error.originalError instanceof AxiosError) {
        const axiosError = error.originalError;
        console.log("Axios URL:", axiosError.config?.url);
        console.log("Axios Method:", axiosError.config?.method?.toUpperCase());
        console.log("Axios Status:", axiosError.response?.status);
        console.log("Axios Response Data:", axiosError.response?.data);
      }
    }
    console.groupEnd();
  }
}
