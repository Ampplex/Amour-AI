import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Modal,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Image,
  Dimensions,
  StyleSheet,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { PersonaItem, updatePublicPersonaDetails } from '../services/personaService';
import { useAuth } from '../context/AuthContext';
import { showAlert } from '../context/AlertContext';

const { width } = Dimensions.get('window');

function CloseIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
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

function GlobeIcon({ size = 14, color = '#D4D4D8' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

interface EditPublicPersonaModalProps {
  visible: boolean;
  persona: PersonaItem | null;
  onClose: () => void;
  onSuccess?: (updated: PersonaItem) => void;
}

export default function EditPublicPersonaModal({
  visible,
  persona,
  onClose,
  onSuccess,
}: EditPublicPersonaModalProps) {
  const { user } = useAuth();
  const [name, setName] = useState('');
  const [tagline, setTagline] = useState('');
  const [greeting, setGreeting] = useState('');
  const [memoryPrompt, setMemoryPrompt] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (persona && visible) {
      setName(persona.name || '');
      setTagline(persona.tagline || '');
      setGreeting(persona.greeting || '');
      setMemoryPrompt(persona.memory_prompt || '');
    }
  }, [persona, visible]);

  if (!visible || !persona) return null;

  const borderColor = persona.border_color || '#F43F5E';

  const handleSave = async () => {
    if (!name.trim()) {
      showAlert('Required Field', 'Please enter a persona name.', [{ text: 'OK' }], 'warning');
      return;
    }

    setIsSaving(true);
    try {
      const res = await updatePublicPersonaDetails(
        persona.id,
        {
          name: name.trim(),
          tagline: tagline.trim(),
          greeting: greeting.trim(),
          memory_prompt: memoryPrompt.trim(),
        },
        user?.id
      );

      if (res.success && res.persona) {
        showAlert(
          'Public Version Updated',
          `"${name.trim()}" has been updated in the public community feed. All users will now see these details.`,
          [{ text: 'OK', style: 'primary' }],
          'success'
        );
        onSuccess?.(res.persona);
        onClose();
      } else {
        showAlert(
          'Update Failed',
          res.error || 'Could not update public persona details. Please try again.',
          [{ text: 'OK' }],
          'danger'
        );
      }
    } catch (err: any) {
      showAlert('Update Error', err?.message || 'Network error updating public version.', [{ text: 'OK' }], 'danger');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={false}
      statusBarTranslucent={true}
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
        {/* Top Header */}
        <View style={styles.header}>
          <TouchableOpacity
            onPress={onClose}
            style={styles.closeBtn}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            activeOpacity={0.7}
          >
            <CloseIcon size={20} color="#FFFFFF" />
          </TouchableOpacity>

          <View style={styles.headerTitleCol}>
            <View style={styles.publicBadgeRow}>
              <GlobeIcon size={12} color="#D4D4D8" />
              <Text style={styles.publicBadgeText}>PUBLIC CANONICAL VERSION</Text>
            </View>
            <Text style={styles.headerTitle}>Edit Public Persona</Text>
          </View>

          <TouchableOpacity
            style={[styles.saveHeaderBtn, isSaving && styles.saveHeaderBtnDisabled]}
            onPress={handleSave}
            disabled={isSaving}
            activeOpacity={0.8}
          >
            {isSaving ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Text style={styles.saveHeaderBtnText}>Save</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Public Notice Banner */}
        <View style={styles.publicNoticeBanner}>
          <Text style={styles.publicNoticeTitle}>Author Public Control</Text>
          <Text style={styles.publicNoticeSubtitle}>
            You own this persona. Changes made here update the canonical version in the public community feed for all users.
          </Text>
        </View>

        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ flex: 1 }}
        >
          <ScrollView
            style={styles.scrollContent}
            contentContainerStyle={styles.scrollInner}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Avatar Row */}
            <View style={styles.avatarPreviewRow}>
              {persona.image_url ? (
                <Image
                  source={{ uri: persona.image_url }}
                  style={[styles.avatarImg, { borderColor }]}
                  fadeDuration={0}
                />
              ) : (
                <View style={[styles.avatarFallback, { backgroundColor: borderColor }]}>
                  <Text style={styles.avatarLetter}>{name.charAt(0).toUpperCase() || 'P'}</Text>
                </View>
              )}
              <View style={styles.avatarInfoCol}>
                <Text style={styles.avatarInfoName} numberOfLines={1}>{name || 'Persona'}</Text>
                <Text style={styles.avatarInfoHandle}>
                  {persona.publisher_handle || (user?.email ? `@${user.email.split('@')[0]}` : '@creator')}
                </Text>
              </View>
            </View>

            {/* Field: Name */}
            <View style={styles.fieldSection}>
              <Text style={styles.fieldLabel}>Persona Name</Text>
              <TextInput
                style={styles.inputSingle}
                value={name}
                onChangeText={setName}
                placeholder="Persona name (e.g. Luke)"
                placeholderTextColor="#71717A"
                maxLength={60}
              />
            </View>

            {/* Field: Tagline */}
            <View style={styles.fieldSection}>
              <Text style={styles.fieldLabel}>Tagline / Role Summary</Text>
              <TextInput
                style={styles.inputSingle}
                value={tagline}
                onChangeText={setTagline}
                placeholder="Short tagline (e.g. The brooding varsity lacrosse captain)"
                placeholderTextColor="#71717A"
                maxLength={120}
              />
            </View>

            {/* Field: Greeting */}
            <View style={styles.fieldSection}>
              <View style={styles.fieldLabelRow}>
                <Text style={styles.fieldLabel}>First Dialogue Script (Opening Line)</Text>
                <Text style={styles.fieldHint}>Public greeting</Text>
              </View>
              <TextInput
                style={[styles.inputMulti, { minHeight: 100 }]}
                value={greeting}
                onChangeText={setGreeting}
                placeholder="The opening line that all users receive when first chatting with this companion..."
                placeholderTextColor="#71717A"
                multiline
                maxLength={1000}
                textAlignVertical="top"
              />
            </View>

            {/* Field: Memory Prompt / Backstory / Personality */}
            <View style={styles.fieldSection}>
              <View style={styles.fieldLabelRow}>
                <Text style={styles.fieldLabel}>Mind & Backstory Profile (Personality)</Text>
                <Text style={styles.fieldHint}>Core roleplay brain</Text>
              </View>
              <TextInput
                style={[styles.inputMulti, { minHeight: 140 }]}
                value={memoryPrompt}
                onChangeText={setMemoryPrompt}
                placeholder="Describe personality, backstory, mannerisms, habits, and secrets that govern how the persona speaks to everyone..."
                placeholderTextColor="#71717A"
                multiline
                maxLength={3000}
                textAlignVertical="top"
              />
            </View>

            <View style={{ height: 40 }} />
          </ScrollView>
        </KeyboardAvoidingView>

        {/* Bottom Save Action Bar */}
        <View style={styles.bottomBar}>
          <TouchableOpacity
            style={styles.cancelBtn}
            onPress={onClose}
            activeOpacity={0.7}
            disabled={isSaving}
          >
            <Text style={styles.cancelBtnText}>Cancel</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.saveBtn, isSaving && styles.saveBtnDisabled]}
            onPress={handleSave}
            disabled={isSaving}
            activeOpacity={0.85}
          >
            {isSaving ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Text style={styles.saveBtnText}>Save Public Version</Text>
            )}
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#171717',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#262628',
  },
  closeBtn: {
    padding: 6,
  },
  headerTitleCol: {
    alignItems: 'center',
  },
  publicBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: 2,
  },
  publicBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#D4D4D8',
    letterSpacing: 0.6,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },
  saveHeaderBtn: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 14,
    minWidth: 60,
    alignItems: 'center',
  },
  saveHeaderBtnDisabled: {
    opacity: 0.5,
  },
  saveHeaderBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0A0A0C',
  },
  publicNoticeBanner: {
    backgroundColor: '#1E1E22',
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C32',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  publicNoticeTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  publicNoticeSubtitle: {
    fontSize: 11.5,
    color: '#9CA3AF',
    lineHeight: 16,
  },
  scrollContent: {
    flex: 1,
  },
  scrollInner: {
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  avatarPreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: '#202022',
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#2E2E32',
    marginBottom: 20,
  },
  avatarImg: {
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 2,
  },
  avatarFallback: {
    width: 50,
    height: 50,
    borderRadius: 25,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarLetter: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  avatarInfoCol: {
    flex: 1,
  },
  avatarInfoName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  avatarInfoHandle: {
    fontSize: 12,
    color: '#9CA3AF',
  },
  fieldSection: {
    marginBottom: 18,
  },
  fieldLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E4E4E7',
    marginBottom: 6,
  },
  fieldHint: {
    fontSize: 11,
    color: '#71717A',
  },
  inputSingle: {
    backgroundColor: '#202022',
    borderWidth: 1,
    borderColor: '#2E2E32',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: '#FFFFFF',
  },
  inputMulti: {
    backgroundColor: '#202022',
    borderWidth: 1,
    borderColor: '#2E2E32',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: '#FFFFFF',
    lineHeight: 20,
  },
  bottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#262628',
    backgroundColor: '#171717',
  },
  cancelBtn: {
    flex: 1,
    backgroundColor: '#262628',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  cancelBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  saveBtn: {
    flex: 2,
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  saveBtnDisabled: {
    opacity: 0.5,
  },
  saveBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0A0A0C',
  },
});
