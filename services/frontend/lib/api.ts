// API client for orchestrator backend

import { RunRequest, RunResponse } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8004';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function runSearch(request: RunRequest): Promise<RunResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        freeText: request.freeText,
        useWebSearch: request.useWebSearch ?? true,
        topK: request.topK ?? 10,
        configId: request.configId ?? 'default',
        webSearchOptions: request.webSearchOptions ?? {
          recency: 'month',
          maxResultsPerTask: 10,
        },
      }),
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = await response.text();
      }
      throw new ApiError(
        `API request failed: ${response.status} ${response.statusText}`,
        response.status,
        errorData
      );
    }

    const data: RunResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(
        'Cannot connect to backend service. Please try again.',
      0
    );
  }

    throw new ApiError(
      `Unexpected error: ${error instanceof Error ? error.message : String(error)}`,
      0
    );
  }
}

export async function healthCheck(): Promise<{ status: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    throw new ApiError(
      'Backend service is not available',
      0
    );
  }
}
