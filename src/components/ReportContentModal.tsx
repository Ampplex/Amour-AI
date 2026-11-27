import React, { useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { submitContentReport } from '../services/reportService';

export interface ReportTarget {
  contentType: 'message' | 'persona';
  contentId?: string;
  personaId?: string;
  personaName?: string;
  reportedText?: string;
}

interface ReportContentModalProps {
  visible: boolean;
  onClose: () => void;
  target: ReportTarget | null;
  userId?: string;
  userEmail?: string;
  token?: string;
  onReportSubmitted?: (reportId?: string) => void;
  onDeleteMessageRequest?: (messageId: string) => void;
}

function FlagIcon({ size = 20, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1v19"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CloseIcon({ size = 18, color = '#A1A1AA' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M18 6L6 18M6 6l12 12"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CheckCircleIcon({ size = 48, color = '#10B981' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M22 11.08V12a10 10 0 1 1-5.93-9.14"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M22 4L12 14.01l-3-3"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

const REPORT_REASONS = [
  'Harmful, violent, or dangerous content',
  'Sexually explicit or inappropriate content',
  'Hate speech, harassment, or bullying',
  'Misinformation or deceptive claims',
  'Spam, repetitive, or low quality',
  'Other policy violation',
];

export default function ReportContentModal({
  visible,
  onClose,
  target,
  userId,
  userEmail,
  token,
  onReportSubmitted,
  onDeleteMessageRequest,
}: ReportContentModalProps) {
  const [selectedReason, setSelectedReason] = useState<string>(REPORT_REASONS[0]);
  const [details, setDetails] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [submittedReportId, setSubmittedReportId] = useState<string | undefined>(undefined);
  const [emailDispatched, setEmailDispatched] = useState<boolean>(false);

  const resetForm = () => {
    setSelectedReason(REPORT_REASONS[0]);
    setDetails('');
    setIsSubmitting(false);
    setIsSuccess(false);
    setSubmittedReportId(undefined);
    setEmailDispatched(false);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = async () => {
    if (!target || !selectedReason) return;
    setIsSubmitting(true);

    try {
      const res = await submitContentReport(
        {
          contentType: target.contentType,
          contentId: target.contentId,
          personaId: target.personaId,
          personaName: target.personaName,
          reportedText: target.reportedText,
          reason: selectedReason,
          details: details.trim(),
          userId,
          reporterEmail: userEmail,
        },
        token
      );

      if (res.success) {
        setIsSuccess(true);
        setSubmittedReportId(res.reportId);
        setEmailDispatched(!!res.emailSent);
        if (onReportSubmitted) {
          onReportSubmitted(res.reportId);
        }
      }
    } catch (err) {
      console.warn('[ReportContentModal] Submission error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteMessage = () => {
    if (target?.contentId && onDeleteMessageRequest) {
      onDeleteMessageRequest(target.contentId);
    }
    handleClose();
  };

  if (!visible || !target) return null;

  const isMessage = target.contentType === 'message';
  const targetLabel = isMessage
    ? `AI Response from ${target.personaName || 'Companion'}`
    : `AI Companion: ${target.personaName || 'Companion'}`;

  return (
    <Modal
      visible={visible}
      transparent={true}
      animationType="fade"
      statusBarTranslucent={true}
      onRequestClose={handleClose}
    >
      <KeyboardAvoidingView
        style={styles.backdrop}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.sheetContainer}>
          {/* Header */}
          <View style={styles.headerRow}>
            <View style={styles.headerLeft}>
              <View style={styles.flagIconBox}>
                <FlagIcon size={16} color="#F43F5E" />
              </View>
              <Text style={styles.headerTitle}>Report AI Content</Text>
            </View>
            <TouchableOpacity
              onPress={handleClose}
              style={styles.closeBtn}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              accessibilityLabel="Close report dialog"
            >
              <CloseIcon size={18} color="#A1A1AA" />
            </TouchableOpacity>
          </View>

          {!isSuccess ? (
            <ScrollView
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={styles.scrollContent}
            >
              {/* Target info pill */}
              <View style={styles.targetInfoPill}>
                <Text style={styles.targetInfoText} numberOfLines={1}>
                  {targetLabel}
                </Text>
              </View>

              {/* Reported snippet preview (if message) */}
              {isMessage && target.reportedText ? (
                <View style={styles.snippetPreviewBox}>
                  <Text style={styles.snippetText} numberOfLines={3}>
                    "{target.reportedText}"
                  </Text>
                </View>
              ) : null}

              {/* Reasons Selection */}
              <Text style={styles.sectionSubtitle}>
                Why are you reporting this AI-generated content?
              </Text>

              <View style={styles.reasonsList}>
                {REPORT_REASONS.map((reason) => {
                  const isSelected = selectedReason === reason;
                  return (
                    <TouchableOpacity
                      key={reason}
                      style={[styles.reasonRow, isSelected && styles.reasonRowSelected]}
                      onPress={() => setSelectedReason(reason)}
                      activeOpacity={0.7}
                    >
                      <View style={[styles.radioCircle, isSelected && styles.radioCircleSelected]}>
                        {isSelected && <View style={styles.radioDot} />}
                      </View>
                      <Text style={[styles.reasonText, isSelected && styles.reasonTextSelected]}>
                        {reason}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {/* Additional Details Input */}
              <Text style={styles.inputLabel}>Additional details (optional)</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Describe what was inappropriate or harmful..."
                placeholderTextColor="#71717A"
                value={details}
                onChangeText={setDetails}
                multiline={true}
                numberOfLines={3}
                maxLength={500}
                textAlignVertical="top"
              />

              {/* Policy note */}
              <Text style={styles.policyNote}>
                Amour AI companions use generative AI models. Reports are reviewed by our moderation team to keep Amour safe.
                {userEmail ? ` A confirmation will be sent to ${userEmail}.` : ''}
              </Text>

              {/* Action Buttons */}
              <View style={styles.actionsRow}>
                <TouchableOpacity
                  style={styles.cancelBtn}
                  onPress={handleClose}
                  activeOpacity={0.7}
                  disabled={isSubmitting}
                >
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.submitBtn, isSubmitting && styles.submitBtnDisabled]}
                  onPress={handleSubmit}
                  activeOpacity={0.8}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <Text style={styles.submitBtnText}>Submit Report</Text>
                  )}
                </TouchableOpacity>
              </View>
            </ScrollView>
          ) : (
            /* Success State */
            <View style={styles.successContainer}>
              <View style={styles.successIconCircle}>
                <CheckCircleIcon size={44} color="#10B981" />
              </View>
              <Text style={styles.successTitle}>Report Submitted</Text>
              <Text style={styles.successMessage}>
                Thank you for helping keep our community safe. Our moderation team has received this report and will review it promptly.
              </Text>

              {emailDispatched && userEmail ? (
                <View style={styles.emailNoticeBox}>
                  <Text style={styles.emailNoticeText}>
                    ✉️ An official acknowledgment with Case ID has been sent to {userEmail}.
                  </Text>
                </View>
              ) : null}

              {isMessage && onDeleteMessageRequest ? (
                <TouchableOpacity
                  style={styles.deleteOptionBtn}
                  onPress={handleDeleteMessage}
                  activeOpacity={0.7}
                >
                  <Text style={styles.deleteOptionText}>
                    Delete this message from chat
                  </Text>
                </TouchableOpacity>
              ) : null}

              <TouchableOpacity
                style={styles.doneBtn}
                onPress={handleClose}
                activeOpacity={0.8}
              >
                <Text style={styles.doneBtnText}>Done</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'flex-end',
  },
  sheetContainer: {
    backgroundColor: '#121216',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: '#27272A',
    maxHeight: '88%',
    paddingBottom: Platform.OS === 'ios' ? 34 : 20,
    overflow: 'hidden',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1F1F24',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  flagIconBox: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: 'rgba(244, 63, 94, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.2,
  },
  closeBtn: {
    padding: 6,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 24,
  },
  targetInfoPill: {
    alignSelf: 'flex-start',
    backgroundColor: '#1C1C22',
    borderWidth: 1,
    borderColor: '#2E2E36',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
    marginBottom: 12,
  },
  targetInfoText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#D4D4D8',
  },
  snippetPreviewBox: {
    backgroundColor: '#16161B',
    borderLeftWidth: 3,
    borderLeftColor: '#F43F5E',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 16,
  },
  snippetText: {
    fontSize: 12,
    fontStyle: 'italic',
    color: '#A1A1AA',
    lineHeight: 17,
  },
  sectionSubtitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E4E4E7',
    marginBottom: 10,
  },
  reasonsList: {
    gap: 8,
    marginBottom: 16,
  },
  reasonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: '#18181E',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#27272A',
  },
  reasonRowSelected: {
    backgroundColor: 'rgba(244, 63, 94, 0.08)',
    borderColor: '#F43F5E',
  },
  radioCircle: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: '#52525B',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  radioCircleSelected: {
    borderColor: '#F43F5E',
  },
  radioDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#F43F5E',
  },
  reasonText: {
    fontSize: 13,
    color: '#D4D4D8',
    flex: 1,
  },
  reasonTextSelected: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#A1A1AA',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  textInput: {
    backgroundColor: '#18181E',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#27272A',
    color: '#FFFFFF',
    fontSize: 13,
    padding: 12,
    minHeight: 70,
    marginBottom: 12,
  },
  policyNote: {
    fontSize: 11,
    color: '#71717A',
    lineHeight: 16,
    marginBottom: 20,
  },
  actionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 13,
    borderRadius: 12,
    backgroundColor: '#1C1C22',
    borderWidth: 1,
    borderColor: '#2E2E36',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#D4D4D8',
  },
  submitBtn: {
    flex: 2,
    paddingVertical: 13,
    borderRadius: 12,
    backgroundColor: '#F43F5E',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#F43F5E',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  successContainer: {
    paddingHorizontal: 24,
    paddingVertical: 32,
    alignItems: 'center',
  },
  successIconCircle: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
  },
  successTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 8,
  },
  successMessage: {
    fontSize: 13,
    lineHeight: 19,
    color: '#A1A1AA',
    textAlign: 'center',
    marginBottom: 16,
  },
  emailNoticeBox: {
    backgroundColor: '#18181E',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#27272A',
    padding: 12,
    width: '100%',
    marginBottom: 18,
  },
  emailNoticeText: {
    fontSize: 12,
    color: '#D4D4D8',
    textAlign: 'center',
  },
  deleteOptionBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.25)',
    marginBottom: 16,
    width: '100%',
    alignItems: 'center',
  },
  deleteOptionText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#EF4444',
  },
  doneBtn: {
    width: '100%',
    paddingVertical: 13,
    borderRadius: 12,
    backgroundColor: '#F43F5E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  doneBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
