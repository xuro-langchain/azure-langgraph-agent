// Authentication utilities for Azure AD integration

export interface AuthTokens {
  'azure-access-token': string;
  'azure-id-token': string;
}

export interface TokenData {
  access_token: string;
  id_token: string;
}

class AuthService {
  private baseUrl = '/api'; // Use Next.js proxy instead of direct backend calls
  private tokenStore: TokenData | null = null;
  private refreshPromise: Promise<TokenData | null> | null = null;

  // Get tokens from backend and store in memory
  private async fetchAndStoreTokens(): Promise<TokenData | null> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/tokens`, {
        method: 'GET',
        credentials: 'include',
      });
      
      if (response.ok) {
        const tokens = await response.json();
        
        this.tokenStore = {
          access_token: tokens.access_token,
          id_token: tokens.id_token,
        };
        return this.tokenStore;
      } else {
        console.log('Error fetching tokens: ', response.statusText);
        this.tokenStore = null;
        return null;
      }
    } catch (error) {
      console.error('🔍 Error querying backend: ', error);
      this.tokenStore = null;
      return null;
    }
  }

  // Get tokens - always fetch fresh tokens from backend
  async getTokens(): Promise<TokenData | null> {
    // If we're already fetching, wait for that to complete
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    // Always fetch fresh tokens from backend
    this.refreshPromise = this.fetchAndStoreTokens();
    const result = await this.refreshPromise;
    this.refreshPromise = null;
    return result;
  }

  // Get auth headers for requests
  async getAuthHeaders(): Promise<AuthTokens | null> {
    const tokens = await this.getTokens();
    if (!tokens) {
      return null;
    }

    return {
      'azure-access-token': tokens.access_token,
      'azure-id-token': tokens.id_token,
    };
  }

  // Enhanced fetch with automatic auth headers
  async authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
    const authHeaders = await this.getAuthHeaders();
    
    const fetchOptions: RequestInit = {
      ...options,
      credentials: 'include',
      headers: {
        ...options.headers,
        ...(authHeaders && authHeaders),
      },
    };

    let response = await fetch(url, fetchOptions);
    
    // If we get a 401 (Unauthorized), try to refresh tokens and retry once
    if (response.status === 401) {
      this.tokenStore = null; // Clear cached tokens
      this.refreshPromise = null; // Clear any pending refresh
      
      const newAuthHeaders = await this.getAuthHeaders();
      if (newAuthHeaders) {
        const retryOptions: RequestInit = {
          ...options,
          credentials: 'include',
          headers: {
            ...options.headers,
            ...newAuthHeaders,
          },
        };
        response = await fetch(url, retryOptions);
      }
    }

    return response;
  }

  async getAuthUrl(): Promise<string> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/login`, {
        method: 'GET',
        credentials: 'include',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to get auth URL: ${response.status}`);
      }
      const data = await response.json();
      return data.auth_url;
    } catch (error) {
      console.error('Error getting auth URL:', error);
      throw error;
    }
  }

  async checkAuthStatus(): Promise<boolean> {
    const tokens = await this.getTokens();
    return tokens !== null;
  }

  async logout(): Promise<void> {
    try {
      await fetch(`${this.baseUrl}/auth/logout`, {
        method: 'GET',
        credentials: 'include',
      });
      // Clear in-memory tokens
      this.tokenStore = null;
      this.refreshPromise = null;
    } catch (error) {
      console.error('Error during logout:', error);
    }
  }
}

export const authService = new AuthService();

export { AuthService }; 