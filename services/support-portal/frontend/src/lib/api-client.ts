/**
 * API client for Support Portal backend
 */

import axios, { AxiosInstance } from 'axios';

export interface Ticket {
  ticket_id: string;
  org_id: string;
  user_id: string;
  subject: string;
  description: string;
  priority: string;
  status: string;
  product_area: string;
  severity?: string;
  tags: string[];
  assigned_to?: string;
  sla_response_target?: string;
  sla_resolution_target?: string;
  sla_breached: boolean;
  first_response_at?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface Comment {
  comment_id: string;
  ticket_id: string;
  user_id: string;
  body: string;
  is_internal: boolean;
  attachments: string[];
  created_at: string;
}

export interface CreateTicketRequest {
  subject: string;
  description: string;
  product_area: string;
  severity?: string;
  tags?: string[];
}

export interface KBArticle {
  article_id: string;
  title: string;
  slug: string;
  category: string;
  excerpt?: string;
  content?: string;
  views: number;
  helpful_votes: number;
  unhelpful_votes?: number;
  updated_at: string;
}

export interface CSATMetrics {
  total_responses: number;
  average_rating: number;
  csat_score: number;
  distribution: Record<string, number>;
  period_days: number;
}

export interface TicketStats {
  period_days: number;
  total_tickets: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

class SupportPortalClient {
  private client: AxiosInstance;

  constructor(baseURL: string = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add auth token interceptor
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  // ==================== Tickets ====================

  async createTicket(request: CreateTicketRequest): Promise<Ticket> {
    const response = await this.client.post<Ticket>('/api/v1/tickets', request);
    return response.data;
  }

  async getTicket(ticketId: string): Promise<Ticket> {
    const response = await this.client.get<Ticket>(`/api/v1/tickets/${ticketId}`);
    return response.data;
  }

  async listTickets(params?: {
    status?: string;
    priority?: string;
    limit?: number;
    offset?: number;
  }): Promise<Ticket[]> {
    const response = await this.client.get<Ticket[]>('/api/v1/tickets', { params });
    return response.data;
  }

  async updateTicket(
    ticketId: string,
    updates: {
      status?: string;
      priority?: string;
      assigned_to?: string;
    }
  ): Promise<Ticket> {
    const response = await this.client.patch<Ticket>(`/api/v1/tickets/${ticketId}`, updates);
    return response.data;
  }

  async cancelTicket(ticketId: string): Promise<void> {
    await this.client.delete(`/api/v1/tickets/${ticketId}`);
  }

  // ==================== Comments ====================

  async createComment(
    ticketId: string,
    body: string,
    isInternal: boolean = false
  ): Promise<Comment> {
    const response = await this.client.post<Comment>(
      `/api/v1/tickets/${ticketId}/comments`,
      { body, is_internal: isInternal }
    );
    return response.data;
  }

  async listComments(ticketId: string): Promise<Comment[]> {
    const response = await this.client.get<Comment[]>(
      `/api/v1/tickets/${ticketId}/comments`
    );
    return response.data;
  }

  // ==================== CSAT ====================

  async submitCSAT(ticketId: string, rating: number, feedback?: string): Promise<void> {
    await this.client.post(`/api/v1/tickets/${ticketId}/csat`, null, {
      params: { rating, feedback },
    });
  }

  async getCSATMetrics(days: number = 30): Promise<CSATMetrics> {
    const response = await this.client.get<CSATMetrics>('/api/v1/csat/metrics', {
      params: { days },
    });
    return response.data;
  }

  // ==================== Knowledge Base ====================

  async searchKB(query: string, limit: number = 10): Promise<KBArticle[]> {
    const response = await this.client.get<KBArticle[]>('/api/v1/kb/search', {
      params: { query, limit },
    });
    return response.data;
  }

  async getArticle(articleId: string): Promise<KBArticle> {
    const response = await this.client.get<KBArticle>(`/api/v1/kb/articles/${articleId}`);
    return response.data;
  }

  async voteArticle(articleId: string, helpful: boolean): Promise<void> {
    await this.client.post(`/api/v1/kb/articles/${articleId}/vote`, null, {
      params: { helpful },
    });
  }

  // ==================== Analytics ====================

  async getTicketStats(days: number = 30): Promise<TicketStats> {
    const response = await this.client.get<TicketStats>('/api/v1/analytics/ticket-stats', {
      params: { days },
    });
    return response.data;
  }
}

export const apiClient = new SupportPortalClient();
