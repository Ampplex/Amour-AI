import React, { useState, useEffect } from 'react';
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
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Rect } from 'react-native-svg';
import {
  getOrCreateUserKey,
  saveLocalMemoryKey,
  generateRecoveryPhrase,
  encryptKeyWithRecoveryPhrase,
  decryptKeyWithRecoveryPhrase,
  uploadKeyBackup,
  fetchKeyBackup,
} from '../services/keyService';

interface MemorySecurityModalProps {
  visible: boolean;
  onClose: () => void;
  userId: string;
  token?: string;
}

function ShieldCheckIcon({ size = 28, color = '#10B981' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M9 12l2 2 4-4"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function KeyIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M21 2l-2 2m-1.5 1.5L16 7l-1.5-1.5L13 7l-1 1 3 3 1-1 1.5 1.5L19 10l1.5-1.5 2-2M7.5 10.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CloseIcon({ size = 20, color = '#9CA3AF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M18 6L6 18M6 6l12 12"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CopyIcon({ size = 16, color = '#9CA3AF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect
        x="9"
        y="9"
        width="13"
        height="13"
        rx="2"
        ry="2"
        stroke={color}
        strokeWidth="2"
      />
      <Path
        d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"
        stroke={color}
        strokeWidth="2"
      />
    </Svg>
  );
}

export function MemorySecurityModal({
  visible,
  onClose,
  userId,
  token,
}: MemorySecurityModalProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'backup' | 'restore'>('overview');
  const [isLoading, setIsLoading] = useState(false);
  const [hasServerBackup, setHasServerBackup] = useState(false);
  const [backupDate, setBackupDate] = useState<string | null>(null);

  // Backup State
  const [generatedPhrase, setGeneratedPhrase] = useState<string | null>(null);
  const [backupSaved, setBackupSaved] = useState(false);

  // Restore State
  const [restoreInput, setRestoreInput] = useState('');
  const [restoreSuccess, setRestoreSuccess] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    if (visible && userId) {
      loadBackupStatus();
    }
  }, [visible, userId]);

  const loadBackupStatus = async () => {
    setIsLoading(true);
    try {
      const res = await fetchKeyBackup(userId, token);
      if (res && res.has_backup) {
        setHasServerBackup(true);
      } else {
        setHasServerBackup(false);
      }
    } catch {
      setHasServerBackup(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartBackup = async () => {
    setIsLoading(true);
    setStatusMessage(null);
    try {
      const phrase = await generateRecoveryPhrase();
      setGeneratedPhrase(phrase);
      const userKey = await getOrCreateUserKey();
      const backupPayload = await encryptKeyWithRecoveryPhrase(userKey, phrase);
      const success = await uploadKeyBackup(userId, backupPayload, token);
      if (success) {
        setBackupSaved(true);
        setHasServerBackup(true);
      } else {
        setStatusMessage('Cloud backup failed to upload. Check connection.');
      }
    } catch (err: any) {
      setStatusMessage(err?.message || 'Failed generating recovery phrase');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestore = async () => {
    if (!restoreInput.trim()) {
      setStatusMessage('Please enter your 12-word recovery phrase.');
      return;
    }
    setIsLoading(true);
    setStatusMessage(null);
    try {
      const backup = await fetchKeyBackup(userId, token);
      if (!backup || !backup.has_backup || !backup.encrypted_blob || !backup.salt || !backup.nonce) {
        throw new Error('No encrypted cloud backup found for this account.');
      }
      const decryptedKey = await decryptKeyWithRecoveryPhrase(
        backup.encrypted_blob,
        backup.salt,
        backup.nonce,
        restoreInput.trim()
      );
      await saveLocalMemoryKey(decryptedKey);
      setRestoreSuccess(true);
      setStatusMessage('Memories successfully restored and unlocked on this device.');
    } catch (err: any) {
      setStatusMessage(err?.message || 'Restore failed. Check your 12 words.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <CloseIcon size={22} color="#9CA3AF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Memory Security</Text>
          <View style={{ width: 40 }} />
        </View>

        {/* Segmented Control */}
        <View style={styles.tabsRow}>
          <TouchableOpacity
            style={[styles.tabButton, activeTab === 'overview' && styles.tabButtonActive]}
            onPress={() => {
              setActiveTab('overview');
              setStatusMessage(null);
            }}
          >
            <Text style={[styles.tabText, activeTab === 'overview' && styles.tabTextActive]}>
              Status
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabButton, activeTab === 'backup' && styles.tabButtonActive]}
            onPress={() => {
              setActiveTab('backup');
              setStatusMessage(null);
            }}
          >
            <Text style={[styles.tabText, activeTab === 'backup' && styles.tabTextActive]}>
              Recovery Phrase
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabButton, activeTab === 'restore' && styles.tabButtonActive]}
            onPress={() => {
              setActiveTab('restore');
              setStatusMessage(null);
            }}
          >
            <Text style={[styles.tabText, activeTab === 'restore' && styles.tabTextActive]}>
              Restore
            </Text>
          </TouchableOpacity>
        </View>

        <KeyboardAvoidingView
          style={styles.keyboardAvoid}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
            {/* TAB: OVERVIEW */}
            {activeTab === 'overview' && (
              <View style={styles.tabContent}>
                <View style={styles.shieldHero}>
                  <View style={styles.shieldCircle}>
                    <ShieldCheckIcon size={44} color="#10B981" />
                  </View>
                  <Text style={styles.heroTitle}>Zero-Knowledge Protected</Text>
                  <Text style={styles.heroSubtitle}>
                    Your companion memories and personal details are encrypted client-side using authenticated
                    AES-256-GCM before saving to Neo4j.
                  </Text>
                </View>

                <View style={styles.card}>
                  <View style={styles.cardRow}>
                    <Text style={styles.cardLabel}>Device Key Storage</Text>
                    <Text style={styles.cardBadgeGreen}>Secure Enclave / Keystore</Text>
                  </View>
                  <View style={styles.divider} />
                  <View style={styles.cardRow}>
                    <Text style={styles.cardLabel}>Encryption Standard</Text>
                    <Text style={styles.cardValue}>AES-256-GCM (Authenticated)</Text>
                  </View>
                  <View style={styles.divider} />
                  <View style={styles.cardRow}>
                    <Text style={styles.cardLabel}>Encrypted Cloud Backup</Text>
                    <Text style={hasServerBackup ? styles.cardBadgeGreen : styles.cardBadgeGray}>
                      {hasServerBackup ? 'Secured' : 'Not Backed Up'}
                    </Text>
                  </View>
                </View>

                <TouchableOpacity
                  style={styles.primaryButton}
                  onPress={() => setActiveTab('backup')}
                  activeOpacity={0.85}
                >
                  <KeyIcon size={18} color="#FFFFFF" />
                  <Text style={styles.primaryButtonText}>
                    {hasServerBackup ? 'View / Renew Recovery Phrase' : 'Backup 12-Word Recovery Phrase'}
                  </Text>
                </TouchableOpacity>
              </View>
            )}

            {/* TAB: BACKUP */}
            {activeTab === 'backup' && (
              <View style={styles.tabContent}>
                <Text style={styles.sectionTitle}>12-Word Recovery Phrase</Text>
                <Text style={styles.sectionSubtitle}>
                  Write down these 12 words in a secure place. Amour AI never knows your words or your encryption key.
                  If you switch phones, you will need this phrase to unlock your memories.
                </Text>

                {generatedPhrase ? (
                  <View style={styles.phraseContainer}>
                    <View style={styles.wordsGrid}>
                      {generatedPhrase.split(' ').map((word, idx) => (
                        <View key={idx} style={styles.wordItem}>
                          <Text style={styles.wordIndex}>{idx + 1}</Text>
                          <Text style={styles.wordText}>{word}</Text>
                        </View>
                      ))}
                    </View>
                    {backupSaved && (
                      <View style={styles.successBanner}>
                        <ShieldCheckIcon size={16} color="#10B981" />
                        <Text style={styles.successText}>Encrypted backup secured in cloud</Text>
                      </View>
                    )}
                  </View>
                ) : (
                  <TouchableOpacity
                    style={styles.primaryButton}
                    onPress={handleStartBackup}
                    disabled={isLoading}
                    activeOpacity={0.85}
                  >
                    {isLoading ? (
                      <ActivityIndicator size="small" color="#FFFFFF" />
                    ) : (
                      <>
                        <KeyIcon size={18} color="#FFFFFF" />
                        <Text style={styles.primaryButtonText}>Generate 12-Word Recovery Phrase</Text>
                      </>
                    )}
                  </TouchableOpacity>
                )}

                {statusMessage && (
                  <Text style={styles.statusErrorText}>{statusMessage}</Text>
                )}
              </View>
            )}

            {/* TAB: RESTORE */}
            {activeTab === 'restore' && (
              <View style={styles.tabContent}>
                <Text style={styles.sectionTitle}>Restore Memories on New Device</Text>
                <Text style={styles.sectionSubtitle}>
                  Enter the 12 words you saved from your previous device to decrypt and unlock your companion memories.
                </Text>

                <TextInput
                  style={styles.inputArea}
                  placeholder="Enter 12 recovery words separated by spaces..."
                  placeholderTextColor="#6B7280"
                  multiline
                  numberOfLines={4}
                  value={restoreInput}
                  onChangeText={setRestoreInput}
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                <TouchableOpacity
                  style={[styles.primaryButton, restoreSuccess && styles.successButton]}
                  onPress={handleRestore}
                  disabled={isLoading || restoreSuccess}
                  activeOpacity={0.85}
                >
                  {isLoading ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <Text style={styles.primaryButtonText}>
                      {restoreSuccess ? 'Memories Unlocked' : 'Restore & Decrypt Memories'}
                    </Text>
                  )}
                </TouchableOpacity>

                {statusMessage && (
                  <Text
                    style={[
                      styles.statusErrorText,
                      restoreSuccess && styles.statusSuccessText,
                    ]}
                  >
                    {statusMessage}
                  </Text>
                )}
              </View>
            )}
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0E14',
  },
  header: {
    height: 54,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1F2937',
  },
  closeButton: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },
  tabsRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 14,
    marginBottom: 8,
    backgroundColor: '#161B26',
    borderRadius: 10,
    padding: 3,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabButtonActive: {
    backgroundColor: '#262F40',
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  tabTextActive: {
    color: '#FFFFFF',
  },
  keyboardAvoid: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  tabContent: {
    gap: 18,
  },
  shieldHero: {
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 12,
  },
  shieldCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  heroTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 8,
  },
  heroSubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 19,
  },
  card: {
    backgroundColor: '#161B26',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#262F40',
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  cardLabel: {
    fontSize: 13,
    color: '#9CA3AF',
  },
  cardValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E5E7EB',
  },
  cardBadgeGreen: {
    fontSize: 12,
    fontWeight: '700',
    color: '#10B981',
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  cardBadgeGray: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9CA3AF',
    backgroundColor: '#262F40',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  divider: {
    height: 1,
    backgroundColor: '#262F40',
    marginVertical: 6,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#EC4899',
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 6,
  },
  successButton: {
    backgroundColor: '#10B981',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    lineHeight: 18,
  },
  phraseContainer: {
    backgroundColor: '#161B26',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#262F40',
    gap: 14,
  },
  wordsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    justifyContent: 'space-between',
  },
  wordItem: {
    width: '31%',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0B0E14',
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1F2937',
  },
  wordIndex: {
    fontSize: 11,
    color: '#6B7280',
    marginRight: 6,
    width: 14,
  },
  wordText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  successText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#10B981',
  },
  inputArea: {
    backgroundColor: '#161B26',
    borderWidth: 1,
    borderColor: '#262F40',
    borderRadius: 12,
    padding: 14,
    color: '#FFFFFF',
    fontSize: 14,
    minHeight: 100,
    textAlignVertical: 'top',
  },
  statusErrorText: {
    fontSize: 13,
    color: '#EF4444',
    textAlign: 'center',
    marginTop: 6,
  },
  statusSuccessText: {
    color: '#10B981',
  },
});
