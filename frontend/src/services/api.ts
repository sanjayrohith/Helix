// API service for communicating with FastAPI backend

import type { SliceConfig, SliceDeploymentResult, SliceStats } from '../types/slice';

const API_BASE_URL = 'http://localhost:8000';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, errorData.detail || 'Request failed');
  }
  return response.json();
}

export async function provisionSlice(intent: string): Promise<SliceDeploymentResult> {
  const response = await fetch(`${API_BASE_URL}/api/slices/provision`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ intent }),
  });
  return handleResponse<SliceDeploymentResult>(response);
}

export async function getAllSlices(): Promise<SliceConfig[]> {
  const response = await fetch(`${API_BASE_URL}/api/slices`);
  return handleResponse<SliceConfig[]>(response);
}

export async function getSlice(sliceId: string): Promise<SliceConfig> {
  const response = await fetch(`${API_BASE_URL}/api/slices/${sliceId}`);
  return handleResponse<SliceConfig>(response);
}

export async function deleteSlice(sliceId: string): Promise<{ message: string; slice_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/slices/${sliceId}`, {
    method: 'DELETE',
  });
  return handleResponse<{ message: string; slice_id: string }>(response);
}

export async function getSliceStats(): Promise<SliceStats> {
  const response = await fetch(`${API_BASE_URL}/api/slices/stats/summary`);
  return handleResponse<SliceStats>(response);
}

export { ApiError };
