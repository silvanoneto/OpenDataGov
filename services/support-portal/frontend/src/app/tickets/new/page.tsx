/**
 * Create New Support Ticket Page
 */

'use client';

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient, CreateTicketRequest } from '@/lib/api-client';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';

export default function NewTicketPage() {
  const router = useRouter();
  const [formData, setFormData] = useState<CreateTicketRequest>({
    subject: '',
    description: '',
    product_area: 'general',
    severity: undefined,
    tags: [],
  });

  // Search KB while typing subject
  const { data: suggestedArticles } = useQuery({
    queryKey: ['kb-search', formData.subject],
    queryFn: () => apiClient.searchKB(formData.subject, 3),
    enabled: formData.subject.length >= 3,
  });

  const createTicketMutation = useMutation({
    mutationFn: (request: CreateTicketRequest) => apiClient.createTicket(request),
    onSuccess: (ticket) => {
      toast.success('Ticket created successfully!');
      router.push(`/tickets/${ticket.ticket_id}`);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create ticket');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createTicketMutation.mutate(formData);
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Create Support Ticket</h1>
        <p className="mt-2 text-sm text-gray-600">
          Submit a new support request to our team
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Form */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="space-y-6 bg-white shadow rounded-lg p-6">
            {/* Subject */}
            <div>
              <label htmlFor="subject" className="block text-sm font-medium text-gray-700">
                Subject <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="subject"
                id="subject"
                required
                value={formData.subject}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="Brief description of the issue"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                name="description"
                id="description"
                required
                rows={8}
                value={formData.description}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="Provide detailed information about the issue, including steps to reproduce if applicable..."
              />
              <p className="mt-2 text-sm text-gray-500">
                Tip: Include error messages, screenshots, and relevant context
              </p>
            </div>

            {/* Product Area */}
            <div>
              <label htmlFor="product_area" className="block text-sm font-medium text-gray-700">
                Product Area <span className="text-red-500">*</span>
              </label>
              <select
                name="product_area"
                id="product_area"
                required
                value={formData.product_area}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="general">General</option>
                <option value="catalog">Data Catalog</option>
                <option value="governance">Governance Engine</option>
                <option value="quality">Data Quality</option>
                <option value="lineage">Lineage Tracking</option>
                <option value="ml_ops">ML Operations</option>
                <option value="federation">Data Federation</option>
                <option value="billing">Billing</option>
                <option value="api">API Integration</option>
                <option value="security">Security</option>
              </select>
            </div>

            {/* Severity (Optional) */}
            <div>
              <label htmlFor="severity" className="block text-sm font-medium text-gray-700">
                Impact Severity
              </label>
              <select
                name="severity"
                id="severity"
                value={formData.severity || ''}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="">Not specified</option>
                <option value="blocking">Blocking - Cannot proceed</option>
                <option value="major">Major - Significant impact</option>
                <option value="minor">Minor - Low impact</option>
                <option value="cosmetic">Cosmetic - Visual issue</option>
              </select>
            </div>

            {/* Submit Button */}
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => router.back()}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createTicketMutation.isPending}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {createTicketMutation.isPending ? 'Creating...' : 'Create Ticket'}
              </button>
            </div>
          </form>
        </div>

        {/* Sidebar - Suggested KB Articles */}
        <div className="lg:col-span-1">
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              💡 Suggested Articles
            </h3>

            {suggestedArticles && suggestedArticles.length > 0 ? (
              <div className="space-y-4">
                {suggestedArticles.map((article) => (
                  <div key={article.article_id} className="border-b border-gray-200 pb-4 last:border-0">
                    <a
                      href={`/kb/${article.article_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
                    >
                      {article.title}
                    </a>
                    <p className="mt-1 text-xs text-gray-500">
                      {article.category} · {article.views} views
                    </p>
                    {article.excerpt && (
                      <p className="mt-2 text-xs text-gray-600 line-clamp-2">
                        {article.excerpt}
                      </p>
                    )}
                  </div>
                ))}
                <p className="text-xs text-gray-500 mt-4">
                  💡 These articles might help solve your issue faster
                </p>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Start typing your subject to see related help articles
              </p>
            )}
          </div>

          {/* SLA Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-6">
            <h4 className="text-sm font-medium text-blue-900 mb-2">
              Response Times
            </h4>
            <ul className="text-xs text-blue-800 space-y-1">
              <li>• <strong>Enterprise P1:</strong> 4 hours</li>
              <li>• <strong>Enterprise P2:</strong> 8 hours</li>
              <li>• <strong>Professional:</strong> 2 business days</li>
              <li>• <strong>Community:</strong> Best effort</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
