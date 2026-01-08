import axios, { AxiosError } from "axios";
import { parseAxiosError, logError } from "./errors";

export const apiClient = axios.create({
  baseURL: "https://mincha.co.kr",
  timeout: 60000, // AI 응답 대기를 위해 60초로 증가
  headers: {
    "Content-Type": "application/json",
  },
});

// 요청 인터셉터 (필요시 토큰 추가)
apiClient.interceptors.request.use(
  (config) => {
    // const token = getToken();
    // if (token) config.headers.Authorization = `Bearer ${token}`;
    if (__DEV__) {
      console.log("[API Request]", config.method?.toUpperCase(), config.url);
      if (config.data) {
        try {
          console.log("[API Request Data]", JSON.stringify(config.data, null, 2));
        } catch {
          console.log("[API Request Data]", config.data);
        }
      }
    }
    return config;
  },
  (error) => {
    const apiError = parseAxiosError(error);
    logError(apiError, "Request Interceptor");
    return Promise.reject(apiError);
  }
);

// 응답 인터셉터 (에러 핸들링)
apiClient.interceptors.response.use(
  (response) => {
    if (__DEV__) {
      console.log("[API Response]", response.status, response.config.url);
      try {
        console.log("[API Response Data]", JSON.stringify(response.data, null, 2));
      } catch (e) {
        console.log("[API Response Data - Decode Error]", e);
        console.log("[API Response Data - Raw]", response.data);
      }
    }
    return response;
  },
  (error: AxiosError) => {
    const apiError = parseAxiosError(error);
    logError(apiError, "Response Interceptor");

    // 공통 에러 처리
    if (error.response?.status === 401) {
      // 인증 에러 처리 (필요시 로그아웃 등)
    }

    return Promise.reject(apiError);
  }
);
