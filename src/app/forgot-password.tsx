import React, { useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { theme } from '../constants/theme';
import AmourLogoVector from '../components/AmourLogoVector';
import { useAuth } from '../context/AuthContext';

export default function ForgotPasswordScreen() {
  const [step, setStep] = useState<'request' | 'reset'>('request');
  const [email, setEmail] = useState<string>('');
  const [code, setCode] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(false);
  const [resendLoading, setResendLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [resendFeedback, setResendFeedback] = useState<string>('');

  const { forgotPassword, resetPassword } = useAuth();

  const handleSendResetEmail = async () => {
    setError('');
    setSuccessMessage('');
    setResendFeedback('');

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    setLoading(true);
    const result = await forgotPassword(email.trim());
    setLoading(false);

    if (result.success) {
      setStep('reset');
    } else {
      setError(result.error || 'Failed to send password reset email.');
    }
  };

  const handleResetPassword = async () => {
    setError('');
    setSuccessMessage('');
    setResendFeedback('');

    if (!code.trim() || code.trim().length < 6) {
      setError('Please enter the 6-digit reset code from your email.');
      return;
    }

    if (!newPassword.trim()) {
      setError('Please enter a new password.');
      return;
    }

    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    const result = await resetPassword(email.trim(), code.trim(), newPassword);
    setLoading(false);

    if (result.success) {
      setSuccessMessage('Password updated successfully. Redirecting to sign in...');
      setTimeout(() => {
        router.replace('/login');
      }, 1200);
    } else {
      setError(result.error || 'Password reset failed. Please check your code.');
    }
  };

  const handleResend = async () => {
    setError('');
    setResendFeedback('');
    if (!email.trim()) return;

    setResendLoading(true);
    const result = await forgotPassword(email.trim());
    setResendLoading(false);

    if (result.success) {
      setResendFeedback('A fresh reset code has been sent to your inbox.');
    } else {
      setError(result.error || 'Failed to resend code.');
    }
  };

  const handleBack = () => {
    if (step === 'reset') {
      setStep('request');
    } else {
      if (router.canGoBack()) {
        router.back();
      } else {
        router.replace('/login');
      }
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Top Bar with Back Button */}
          <View style={styles.topBar}>
            <TouchableOpacity
              onPress={handleBack}
              style={styles.backButton}
              activeOpacity={0.7}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Text style={styles.backButtonText}>
                ‹ {step === 'reset' ? 'Change Email' : 'Back to Sign In'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Centered App Logo */}
          <View style={styles.headerEmblem}>
            <AmourLogoVector size={135} showText={false} animated={false} />
          </View>

          {step === 'request' ? (
            <>
              {/* Header */}
              <View style={styles.header}>
                <Text style={styles.title}>Reset Password</Text>
                <Text style={styles.subtitle}>
                  Enter your email address and we'll send you instructions and a 6-digit code to reset your password.
                </Text>
              </View>

              {/* Error Banner */}
              {error ? (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {/* Form */}
              <View style={styles.form}>
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>Email Address</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="name@example.com"
                    placeholderTextColor={theme.colors.textMuted}
                    value={email}
                    onChangeText={setEmail}
                    autoCapitalize="none"
                    keyboardType="email-address"
                    autoCorrect={false}
                    autoFocus
                  />
                </View>

                {/* Submit */}
                <TouchableOpacity
                  style={styles.submitButton}
                  onPress={handleSendResetEmail}
                  disabled={loading}
                  activeOpacity={0.85}
                >
                  {loading ? (
                    <ActivityIndicator color={theme.colors.primaryText} />
                  ) : (
                    <Text style={styles.submitButtonText}>Send Reset Code</Text>
                  )}
                </TouchableOpacity>

                <TouchableOpacity
                  onPress={() => router.replace('/login')}
                  style={styles.cancelButton}
                  activeOpacity={0.7}
                >
                  <Text style={styles.cancelButtonText}>Remember your password? Sign in</Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            <>
              {/* Header */}
              <View style={styles.header}>
                <View style={styles.badgeRow}>
                  <View style={styles.stepBadge}>
                    <Text style={styles.stepBadgeText}>PASSWORD RESET</Text>
                  </View>
                </View>
                <Text style={styles.title}>Enter Reset Code</Text>
                <Text style={styles.subtitle}>
                  We sent a 6-digit code to <Text style={styles.boldEmail}>{email}</Text>.
                </Text>
              </View>

              {/* Error Banner */}
              {error ? (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {/* Password Updated Banner */}
              {successMessage ? (
                <View style={styles.successContainer}>
                  <Text style={styles.successText}>{successMessage}</Text>
                </View>
              ) : null}

              {/* Form */}
              <View style={styles.form}>
                {/* 6-Digit Code */}
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>6-Digit Code</Text>
                  <TextInput
                    style={styles.codeInput}
                    placeholder="123456"
                    placeholderTextColor={theme.colors.textMuted}
                    value={code}
                    onChangeText={(val) => setCode(val.replace(/[^0-9]/g, '').slice(0, 6))}
                    keyboardType="number-pad"
                    maxLength={6}
                    autoFocus
                  />
                </View>

                {/* New Password */}
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>New Password</Text>
                  <View style={styles.passwordContainer}>
                    <TextInput
                      style={styles.passwordInput}
                      placeholder="At least 6 characters"
                      placeholderTextColor={theme.colors.textMuted}
                      value={newPassword}
                      onChangeText={setNewPassword}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                    <TouchableOpacity
                      onPress={() => setShowPassword(!showPassword)}
                      style={styles.eyeButton}
                      activeOpacity={0.7}
                    >
                      <Text style={styles.eyeButtonText}>
                        {showPassword ? 'Hide' : 'Show'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Confirm New Password */}
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>Confirm New Password</Text>
                  <View style={styles.passwordContainer}>
                    <TextInput
                      style={styles.passwordInput}
                      placeholder="Re-enter new password"
                      placeholderTextColor={theme.colors.textMuted}
                      value={confirmPassword}
                      onChangeText={setConfirmPassword}
                      secureTextEntry={!showConfirmPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                    <TouchableOpacity
                      onPress={() => setShowConfirmPassword(!showConfirmPassword)}
                      style={styles.eyeButton}
                      activeOpacity={0.7}
                    >
                      <Text style={styles.eyeButtonText}>
                        {showConfirmPassword ? 'Hide' : 'Show'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Submit Reset Button */}
                <TouchableOpacity
                  style={styles.submitButton}
                  onPress={handleResetPassword}
                  disabled={loading}
                  activeOpacity={0.85}
                >
                  {loading ? (
                    <ActivityIndicator color={theme.colors.primaryText} />
                  ) : (
                    <Text style={styles.submitButtonText}>Update Password</Text>
                  )}
                </TouchableOpacity>

                {/* Resend button */}
                <TouchableOpacity
                  style={styles.resendButton}
                  onPress={handleResend}
                  disabled={resendLoading}
                  activeOpacity={0.7}
                >
                  {resendLoading ? (
                    <ActivityIndicator color={theme.colors.text} size="small" />
                  ) : (
                    <Text style={styles.resendButtonText}>Resend Code</Text>
                  )}
                </TouchableOpacity>

                {resendFeedback ? (
                  <Text style={styles.resendFeedbackText}>{resendFeedback}</Text>
                ) : null}
              </View>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  topBar: {
    paddingTop: Platform.OS === 'android' ? 6 : 4,
    paddingBottom: 2,
    justifyContent: 'center',
  },
  backButton: {
    paddingVertical: 6,
    paddingHorizontal: 0,
    alignSelf: 'flex-start',
  },
  backButtonText: {
    color: theme.colors.textSecondary,
    fontSize: 16,
    fontWeight: '500',
  },
  headerEmblem: {
    alignItems: 'center',
    marginTop: 6,
    marginBottom: 8,
  },
  header: {
    marginTop: 16,
    marginBottom: 24,
  },
  badgeRow: {
    marginBottom: 10,
  },
  stepBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(244, 63, 94, 0.15)',
    borderColor: 'rgba(244, 63, 94, 0.35)',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  stepBadgeText: {
    color: '#FB7185',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
  },
  title: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 30,
    color: theme.colors.text,
    letterSpacing: 0.3,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: theme.colors.textSecondary,
    lineHeight: 22,
  },
  boldEmail: {
    color: theme.colors.text,
    fontWeight: '700',
  },
  errorContainer: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderWidth: 1,
    borderColor: theme.colors.error,
    borderRadius: theme.radius.sm,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    color: theme.colors.error,
    fontSize: 13,
    fontWeight: '500',
  },
  successContainer: {
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.3)',
    borderRadius: theme.radius.sm,
    padding: 12,
    marginBottom: 16,
  },
  successText: {
    color: '#FB7185',
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
  resendFeedbackText: {
    color: '#A1A1AA',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 10,
    letterSpacing: 0.2,
  },
  form: {
    gap: 18,
  },
  inputGroup: {
    gap: 8,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: theme.colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  input: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: theme.colors.text,
    fontSize: 16,
  },
  codeInput: {
    backgroundColor: theme.colors.surface,
    borderColor: 'rgba(244, 63, 94, 0.5)',
    borderWidth: 1.5,
    borderRadius: theme.radius.md,
    paddingHorizontal: 16,
    paddingVertical: 16,
    color: theme.colors.text,
    fontSize: 26,
    fontWeight: '700',
    letterSpacing: 10,
    textAlign: 'center',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    paddingHorizontal: 16,
  },
  passwordInput: {
    flex: 1,
    paddingVertical: 14,
    color: theme.colors.text,
    fontSize: 16,
  },
  eyeButton: {
    paddingVertical: 8,
    paddingLeft: 8,
  },
  eyeButtonText: {
    color: theme.colors.textSecondary,
    fontSize: 14,
    fontWeight: '500',
  },
  submitButton: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
  },
  submitButtonText: {
    color: theme.colors.primaryText,
    fontFamily: 'ChangaOne-Regular',
    fontSize: 17,
    letterSpacing: 0.2,
  },
  resendButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.12)',
    borderRadius: theme.radius.md,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  resendButtonText: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  cancelButton: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  cancelButtonText: {
    color: theme.colors.textSecondary,
    fontSize: 14,
    fontWeight: '500',
  },
});
