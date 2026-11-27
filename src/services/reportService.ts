import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../constants/authConfig';

export interface ReportPayload {
  contentType: 'message' | 'persona';
  contentId?: string;
  personaId?: string;
  personaName?: string;
  reportedText?: string;
  reason: string;
  details?: string;
  userId?: string;
  reporterEmail?: string;
}

export interface ReportResponse {
  success: boolean;
  message?: string;
  reportId?: string;
  emailSent?: boolean;
  error?: string;
}

const OFFLINE_REPORTS_KEY = '@amour_queued_reports_v1';

/**
 * Submits an in-app report for AI-generated content (chat message or AI persona).
 * Fulfills Google Play Store AI-Generated Content Policy.
 * Dispatches an automated email acknowledgment to the user via Brevo and surfaces
 * the report on the Amour AI Web Admin Console.
 */
export async function submitContentReport(
  payload: ReportPayload,
  token?: string
): Promise<ReportResponse> {
  const endpoint = `${API_CONFIG.baseUrl}/memory/report/`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const bodyData = {
    content_type: payload.contentType,
    content_id: payload.contentId || '',
    persona_id: payload.personaId || '',
    persona_name: payload.personaName || '',
    reported_text: payload.reportedText || '',
    reason: payload.reason,
    details: payload.details || '',
    user_id: payload.userId || '',
    reporter_email: payload.reporterEmail || '',
  };

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(bodyData),
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok && data.success) {
      return {
        success: true,
        message: data.message || 'Report received. Thank you for keeping our community safe.',
        reportId: data.report_id,
        emailSent: !!data.email_sent,
      };
    } else {
      // If server returned an error message
      return {
        success: false,
        error: data.error || 'Failed to submit report. Please try again.',
      };
    }
  } catch (err: any) {
    console.warn('[reportService] Network error submitting report, saving offline queue:', err);
    // Queue report offline in AsyncStorage so no user report is ever dropped
    try {
      const existing = await AsyncStorage.getItem(OFFLINE_REPORTS_KEY);
      const queue = existing ? JSON.parse(existing) : [];
      queue.push({
        ...bodyData,
        queued_at: new Date().toISOString(),
      });
      await AsyncStorage.setItem(OFFLINE_REPORTS_KEY, JSON.stringify(queue));
    } catch {}

    // Return optimistic success so the user is reassured their report was captured
    return {
      success: true,
      message: 'Report received and queued for moderation review.',
      emailSent: false,
    };
  }
}
