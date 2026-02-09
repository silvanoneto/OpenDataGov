/**
 * Support Portal Home Page - Ticket List
 */

'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient, Ticket } from '@/lib/api-client';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import toast from 'react-hot-toast';

const STATUS_COLORS = {
  new: 'bg-blue-100 text-blue-800',
  open: 'bg-yellow-100 text-yellow-800',
  pending: 'bg-purple-100 text-purple-800',
  solved: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-800',
  cancelled: 'bg-red-100 text-red-800',
};

const PRIORITY_COLORS = {
  p1_critical: 'bg-red-600 text-white',
  p2_high: 'bg-orange-500 text-white',
  p3_normal: 'bg-blue-500 text-white',
  p4_low: 'bg-gray-400 text-white',
  urgent: 'bg-red-500 text-white',
  high: 'bg-orange-400 text-white',
  normal: 'bg-blue-400 text-white',
};

export default function HomePage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>();

  const { data: tickets, isLoading, error } = useQuery({
    queryKey: ['tickets', statusFilter, priorityFilter],
    queryFn: () => apiClient.listTickets({ status: statusFilter, priority: priorityFilter }),
  });

  if (error) {
    toast.error('Failed to load tickets');
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Support Tickets</h1>
          <p className="mt-2 text-sm text-gray-600">
            Manage and track your support requests
          </p>
        </div>
        <Link
          href="/tickets/new"
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700"
        >
          Create New Ticket
        </Link>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Status
            </label>
            <select
              value={statusFilter || ''}
              onChange={(e) => setStatusFilter(e.target.value || undefined)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="open">Open</option>
              <option value="pending">Pending</option>
              <option value="solved">Solved</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Priority
            </label>
            <select
              value={priorityFilter || ''}
              onChange={(e) => setPriorityFilter(e.target.value || undefined)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              <option value="">All Priorities</option>
              <option value="p1_critical">P1 Critical</option>
              <option value="p2_high">P2 High</option>
              <option value="p3_normal">P3 Normal</option>
              <option value="p4_low">P4 Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* Ticket List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          <p className="mt-4 text-gray-600">Loading tickets...</p>
        </div>
      ) : tickets && tickets.length > 0 ? (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {tickets.map((ticket) => (
              <li key={ticket.ticket_id}>
                <Link
                  href={`/tickets/${ticket.ticket_id}`}
                  className="block hover:bg-gray-50 transition"
                >
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              PRIORITY_COLORS[ticket.priority as keyof typeof PRIORITY_COLORS] ||
                              'bg-gray-400 text-white'
                            }`}
                          >
                            {ticket.priority.toUpperCase()}
                          </span>
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              STATUS_COLORS[ticket.status as keyof typeof STATUS_COLORS] ||
                              'bg-gray-100 text-gray-800'
                            }`}
                          >
                            {ticket.status.toUpperCase()}
                          </span>
                          {ticket.sla_breached && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                              SLA BREACHED
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-sm font-medium text-gray-900 truncate">
                          {ticket.subject}
                        </p>
                        <p className="mt-1 text-sm text-gray-500">
                          #{ticket.ticket_id.slice(0, 8)} · {ticket.product_area}
                        </p>
                      </div>
                      <div className="ml-4 flex-shrink-0 text-right">
                        <p className="text-sm text-gray-500">
                          Created {formatDistanceToNow(new Date(ticket.created_at), { addSuffix: true })}
                        </p>
                        {ticket.sla_response_target && !ticket.first_response_at && (
                          <p className="mt-1 text-xs text-orange-600">
                            Response due {formatDistanceToNow(new Date(ticket.sla_response_target), { addSuffix: true })}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="text-center py-12 bg-white shadow rounded-lg">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No tickets</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating a new support ticket.
          </p>
          <div className="mt-6">
            <Link
              href="/tickets/new"
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
            >
              Create Ticket
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
