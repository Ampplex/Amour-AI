import React, { useState, useEffect } from 'react';
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
import { router, useLocalSearchParams } from 'expo-router';
import { theme } from '../constants/theme';
import AmourLogoVector from '../components/AmourLogoVector';
import GoogleIcon from '../components/GoogleIcon';
import { useAuth } from '../context/AuthContext';

export default function SignupScreen() {
  const params = useLocalSearchParams<{ prefillEmail?: string; initialStep?: string }>();

  const [step, setStep] = useState<'form' | 'confirm'>(
    params.initialStep === 'confirm' ? 'confirm' : 'form'
  );
  const [name, setName] = useState<string>('');
  const [email, setEmail] = useState<string>(params.prefillEmail || '');
  const [password, setPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [code, setCode] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(false);
  const [resendLoading, setResendLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [infoMessage, setInfoMessage] = useState<string>('');
  const [resendFeedback, setResendFeedback] = useState<string>('');

  const {
    user,
    signUpWithGoogle,
    signUpWithEmail,
    confirmEmail,
    resendVerification,
    loading: googleLoading,
    error: googleError,
    pendingGoogleSession,
    completeGoogleDevSession,
    dismissPendingSession,
  } = useAuth();

  useEffect(() => {
    if (user) {
      router.replace('/(tabs)');
    }
  }, [user]);

  const handleGoogleSignUp = async () => {
    const loggedInUser = await signUpWithGoogle();
    if (loggedInUser) {
      router.replace('/(tabs)');
    }
  };

  const handleSignup = async () => {
    setError('');
    setInfoMessage('');

    if (!name.trim() || !email.trim() || !password.trim() || !confirmPassword.trim()) {
      setError('Please fill in all fields.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    const result = await signUpWithEmail(name, email, password);
    setLoading(false);

    if (result.success) {
      setStep('confirm');
      setInfoMessage(
        result.message ||
          `We sent a confirmation link and a 6-digit code to ${email}. Tap the link in your email or enter the code below to complete your registration.`
      );
    } else {
      setError(result.error || 'Failed to submit registration. Please try again.');
    }
  };

  const handleConfirmCode = async () => {
    setError('');
    setResendFeedback('');

    if (!code.trim() || code.trim().length < 6) {
      setError('Please enter the 6-digit confirmation code from your email.');
      return;
    }

    setLoading(true);
    const result = await confirmEmail(email, code.trim());
    setLoading(false);

    if (result.success) {
      router.replace('/(tabs)');
    } else {
      setError(result.error || 'Invalid or expired confirmation code.');
    }
  };

  const handleResend = async () => {
    setError('');
    setResendFeedback('');
    if (!email.trim()) {
      setError('Email address is missing.');
      return;
    }

    setResendLoading(true);
    const result = await resendVerification(email);
    setResendLoading(false);

    if (result.success) {
      setResendFeedback('A fresh confirmation link & code has been sent to your email.');
    } else {
      setError(result.error || 'Failed to resend confirmation email.');
    }
  };

  const handleBackToLogin = () => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/login');
    }
  };

  const displayError = error || googleError;

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
              onPress={step === 'confirm' ? () => setStep('form') : handleBackToLogin}
              style={styles.backButton}
              activeOpacity={0.7}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Text style={styles.backButtonText}>
                ‹ {step === 'confirm' ? 'Edit Details' : 'Back'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Centered App Logo */}
          <View style={styles.headerEmblem}>
            <AmourLogoVector size={135} showText={false} animated={false} />
          </View>

          {step === 'form' ? (
            <>
              {/* Heading */}
              <View style={styles.header}>
                <Text style={styles.title}>Create Account</Text>
                <Text style={styles.subtitle}>
                  Experience private, neural intelligence built exclusively for you.
                </Text>
              </View>

              {/* Error Message */}
              {displayError ? (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{displayError}</Text>
                </View>
              ) : null}

              {/* Input Form */}
              <View style={styles.form}>
                {/* Full Name */}
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>Full Name</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Jane Doe"
                    placeholderTextColor={theme.colors.textMuted}
                    value={name}
                    onChangeText={setName}
                    autoCapitalize="words"
                    autoCorrect={false}
                  />
                </View>

                {/* Email */}
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
                  />
                </View>

                {/* Password */}
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>Password</Text>
                  <View style={styles.passwordContainer}>
                    <TextInput
                      style={styles.passwordInput}
                      placeholder="At least 6 characters"
                      placeholderTextColor={theme.colors.textMuted}
                      value={password}
                      onChangeText={setPassword}
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

                {/* Confirm Password */}
                <View style={styles.inputGroup}>
                  <Text style={styles.label}>Confirm Password</Text>
                  <View style={styles.passwordContainer}>
                    <TextInput
                      style={styles.passwordInput}
                      placeholder="Repeat your password"
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

                {/* Submit Button */}
                <TouchableOpacity
                  style={styles.submitButton}
                  onPress={handleSignup}
                  disabled={loading || googleLoading}
                  activeOpacity={0.85}
                >
                  {loading ? (
                    <ActivityIndicator color={theme.colors.primaryText} />
                  ) : (
                    <Text style={styles.submitButtonText}>Continue</Text>
                  )}
                </TouchableOpacity>
              </View>

              {/* Terms text */}
              <Text style={styles.termsText}>
                By creating an account, you agree to Amour AI's{' '}
                <Text style={styles.termsLink}>Terms of Service</Text> and{' '}
                <Text style={styles.termsLink}>Privacy Policy</Text>.
              </Text>

              {/* Divider */}
              <View style={styles.dividerRow}>
                <View style={styles.dividerLine} />
                <Text style={styles.dividerText}>or continue with</Text>
                <View style={styles.dividerLine} />
              </View>

              {/* Google Sign-Up */}
              <TouchableOpacity
                style={styles.googleButton}
                onPress={handleGoogleSignUp}
                disabled={googleLoading || loading}
                activeOpacity={0.8}
              >
                {googleLoading ? (
                  <ActivityIndicator color={theme.colors.text} size="small" />
                ) : (
                  <>
                    <GoogleIcon size={18} />
                    <Text style={styles.googleButtonText}>Sign up with Google</Text>
                  </>
                )}
              </TouchableOpacity>

              {/* Footer Navigation */}
              <View style={styles.footerRow}>
                <Text style={styles.footerText}>Already have an account?</Text>
                <TouchableOpacity onPress={handleBackToLogin} activeOpacity={0.7}>
                  <Text style={styles.footerLink}> Sign in</Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            /* STEP 2: EMAIL CONFIRMATION */
            <>
              <View style={styles.header}>
                <View style={styles.badgeRow}>
                  <View style={styles.stepBadge}>
                    <Text style={styles.stepBadgeText}>VERIFICATION REQUIRED</Text>
                  </View>
                </View>
                <Text style={styles.title}>Confirm Your Email</Text>
                <Text style={styles.subtitle}>
                  We sent a confirmation link and 6-digit code to{' '}
                  <Text style={styles.boldEmail}>{email}</Text>.
                </Text>
              </View>

              {displayError ? (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{displayError}</Text>
                </View>
              ) : null}

              <View style={styles.form}>
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
                  <Text style={styles.codeHint}>
                    Check your spam or junk folder if you don't see it within 1 minute.
                  </Text>
                </View>

                {/* Confirm Code Button */}
                <TouchableOpacity
                  style={styles.submitButton}
                  onPress={handleConfirmCode}
                  disabled={loading}
                  activeOpacity={0.85}
                >
                  {loading ? (
                    <ActivityIndicator color={theme.colors.primaryText} />
                  ) : (
                    <Text style={styles.submitButtonText}>Confirm & Complete Signup</Text>
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
                    <Text style={styles.resendButtonText}>Resend Email</Text>
                  )}
                </TouchableOpacity>

                {resendFeedback ? (
                  <Text style={styles.resendFeedbackText}>{resendFeedback}</Text>
                ) : null}

                {/* Already confirmed link button */}
                <TouchableOpacity
                  style={styles.secondaryLinkButton}
                  onPress={handleBackToLogin}
                  activeOpacity={0.7}
                >
                  <Text style={styles.secondaryLinkText}>
                    Clicked link in email? Proceed to Sign In ›
                  </Text>
                </TouchableOpacity>
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
  codeHint: {
    color: theme.colors.textMuted,
    fontSize: 12,
    marginTop: 4,
    textAlign: 'center',
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
  secondaryLinkButton: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  secondaryLinkText: {
    color: theme.colors.textSecondary,
    fontSize: 14,
    fontWeight: '500',
  },
  termsText: {
    fontSize: 12,
    color: theme.colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    marginTop: 14,
  },
  termsLink: {
    color: theme.colors.primary,
    textDecorationLine: 'underline',
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 22,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: theme.colors.border,
  },
  dividerText: {
    paddingHorizontal: 16,
    fontSize: 13,
    color: theme.colors.textMuted,
    textTransform: 'lowercase',
  },
  googleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    paddingVertical: 14,
    gap: 12,
  },
  googleButtonText: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 22,
  },
  footerText: {
    color: theme.colors.textSecondary,
    fontSize: 14,
  },
  footerLink: {
    color: theme.colors.primary,
    fontSize: 14,
    fontWeight: '600',
  },
});
