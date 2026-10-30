import React from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  ScrollView,
  TouchableOpacity,
  Image,
  Dimensions,
  Platform,
  Share,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Circle } from 'react-native-svg';
import MarkdownText from './MarkdownText';
import { PersonaItem } from '../services/personaService';

const { width } = Dimensions.get('window');

interface PersonaDetailModalProps {
  visible: boolean;
  persona: PersonaItem | null;
  onClose: () => void;
  onInitiateChat: (persona: PersonaItem) => void;
  onDelete?: (id: string, name: string) => void;
}

// Clean Minimalist SVG Vectors - Strictly Zero Emojis
function CloseIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function BrainIcon({ size = 15, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M9.5 2A2.5 2.5 0 0 0 7 4.5V5A3 3 0 0 0 4 8v1a3 3 0 0 0-1 2.25c0 1.25.75 2.3 1.83 2.75A3 3 0 0 0 4 16v1a3 3 0 0 0 3 3h.5A2.5 2.5 0 0 0 10 22h.5a2.5 2.5 0 0 0 2.5-2.5V19a2.5 2.5 0 0 0-2.5-2.5H10v-3h1.5A2.5 2.5 0 0 0 14 11V8.5A2.5 2.5 0 0 0 11.5 6H10V4.5A2.5 2.5 0 0 0 7.5 2h2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M14.5 2A2.5 2.5 0 0 1 17 4.5V5a3 3 0 0 1 3 3v1a3 3 0 0 1 1 2.25c0 1.25-.75 2.3-1.83 2.75A3 3 0 0 1 20 16v1a3 3 0 0 1-3 3h-.5A2.5 2.5 0 0 1 14 22h-.5a2.5 2.5 0 0 1-2.5-2.5V19a2.5 2.5 0 0 1 2.5-2.5H14v-3h-1.5A2.5 2.5 0 0 1 10 11V8.5A2.5 2.5 0 0 1 12.5 6H14V4.5A2.5 2.5 0 0 1 16.5 2h-2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function DialogueIcon({ size = 15, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function ShieldLockIcon({ size = 12, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx="12" cy="11" r="1.5" fill={color} />
      <Path d="M12 12.5V15" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </Svg>
  );
}

function GlobeIcon({ size = 12, color = '#10B981' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth="2" />
      <Path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" stroke={color} strokeWidth="1.8" />
    </Svg>
  );
}

function TrashIcon({ size = 16, color = '#EF4444' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M10 11v6M14 11v6" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </Svg>
  );
}

function MessageIcon({ size = 16, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill={color} />
    </Svg>
  );
}

function ShareIcon({ size = 17, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M22 2L11 13"
        stroke={color}
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M22 2L15 22L11 13L2 9L22 2Z"
        stroke={color}
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function formatDate(isoString?: string): string {
  if (!isoString) return 'Active';
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return 'Active';
  }
}

export default function PersonaDetailModal({
  visible,
  persona,
  onClose,
  onInitiateChat,
  onDelete,
}: PersonaDetailModalProps) {
  if (!persona) return null;

  const borderColor = persona.border_color || '#F43F5E';
  const isPrivate = persona.visibility === 'private';
  const createdDate = formatDate(persona.created_at);

  const handleShare = async () => {
    try {
      const shareUrl = `https://amour.ai/p/${persona.id}`;
      const intro = persona.tagline || persona.greeting || 'Meet my AI companion on Amour!';
      await Share.share({
        title: `Chat with ${persona.name}`,
        message: `Chat with ${persona.name} on Amour AI!\n\n"${intro}"\n\n${shareUrl}`,
      });
    } catch (err) {
      console.warn('[Share] Error sharing persona:', err);
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
        {/* Top Navigation Header */}
        <View style={styles.topBar}>
          <TouchableOpacity
            style={styles.closeBtn}
            onPress={onClose}
            activeOpacity={0.7}
            accessibilityLabel="Close persona details"
          >
            <CloseIcon size={18} color="#FFFFFF" />
          </TouchableOpacity>

          <Text style={styles.topBarTitle}>PROFILE</Text>

          <View style={styles.topBarRight}>
            <TouchableOpacity
              style={styles.headerActionBtn}
              onPress={handleShare}
              activeOpacity={0.7}
              accessibilityLabel="Share persona"
            >
              <ShareIcon size={17} color="#FFFFFF" />
            </TouchableOpacity>

            {onDelete ? (
              <TouchableOpacity
                style={styles.deleteHeaderBtn}
                onPress={() => {
                  onClose();
                  setTimeout(() => {
                    onDelete(persona.id, persona.name);
                  }, 150);
                }}
                activeOpacity={0.7}
                accessibilityLabel="Delete persona"
              >
                <TrashIcon size={18} color="#EF4444" />
              </TouchableOpacity>
            ) : null}
          </View>
        </View>

        {/* Scrollable Details Body */}
        <ScrollView
          style={styles.scrollBody}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Hero Portrait Section */}
          <View style={styles.heroSection}>
            <View style={[styles.avatarFrame, { borderColor }]}>
              {persona.image_url ? (
                <Image source={{ uri: persona.image_url }} style={styles.avatarImage} />
              ) : (
                <View style={[styles.avatarFallback, { backgroundColor: borderColor + '20' }]}>
                  <Text style={[styles.avatarInitial, { color: borderColor }]}>
                    {persona.name ? persona.name.charAt(0).toUpperCase() : 'A'}
                  </Text>
                </View>
              )}
            </View>

            <Text style={styles.heroName}>{persona.name}</Text>

            {persona.tagline ? (
              <Text style={styles.heroTagline}>{persona.tagline}</Text>
            ) : null}

            {/* Badges Row */}
            <View style={styles.badgesRow}>
              {/* Visibility Badge */}
              <View
                style={[
                  styles.badge,
                  {
                    backgroundColor: isPrivate ? 'rgba(244, 63, 94, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                    borderColor: isPrivate ? 'rgba(244, 63, 94, 0.35)' : 'rgba(16, 185, 129, 0.35)',
                  },
                ]}
              >
                {isPrivate ? <ShieldLockIcon size={11} color="#F43F5E" /> : <GlobeIcon size={11} color="#10B981" />}
                <Text style={[styles.badgeText, { color: isPrivate ? '#F43F5E' : '#10B981' }]}>
                  {isPrivate ? 'Private' : 'Community'}
                </Text>
              </View>

              {/* Creator Badge */}
              <View style={styles.neutralBadge}>
                <Text style={styles.neutralBadgeText}>
                  {persona.creator_name || 'Created by you'}
                </Text>
              </View>

              {/* Date Badge */}
              <View style={styles.neutralBadge}>
                <Text style={styles.neutralBadgeText}>{createdDate}</Text>
              </View>
            </View>
          </View>

          {/* Section: Opening Dialogue / First Message */}
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeader}>
              <DialogueIcon size={15} color={borderColor} />
              <Text style={styles.sectionLabel}>FIRST MESSAGE</Text>
            </View>
            <View style={[styles.dialogueBox, { borderLeftColor: borderColor }]}>
              {persona.greeting ? (
                <MarkdownText content={persona.greeting} style={styles.dialogueText} />
              ) : (
                <Text style={styles.emptyFieldText}>No greeting message provided.</Text>
              )}
            </View>
          </View>

          {/* Section: Core Memory Profile & Mind */}
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeader}>
              <BrainIcon size={15} color={borderColor} />
              <Text style={styles.sectionLabel}>PERSONALITY AND STORY</Text>
            </View>
            <View style={styles.memoryBox}>
              {persona.memory_prompt ? (
                <Text style={styles.memoryText}>{persona.memory_prompt}</Text>
              ) : (
                <Text style={styles.emptyFieldText}>No backstory added yet.</Text>
              )}
            </View>
          </View>

          {/* Section: Simple Details Card */}
          <View style={styles.specsCard}>
            <Text style={styles.specsTitle}>ABOUT THIS COMPANION</Text>
            <View style={styles.specRow}>
              <Text style={styles.specKey}>Who can chat</Text>
              <Text style={styles.specValue}>
                {isPrivate ? 'Only You (Private)' : 'Community Shared'}
              </Text>
            </View>
            <View style={styles.specDivider} />
            <View style={styles.specRow}>
              <Text style={styles.specKey}>Date Created</Text>
              <Text style={styles.specValue}>{createdDate}</Text>
            </View>
          </View>
        </ScrollView>

        {/* Bottom Floating Action Bar */}
        <View style={styles.actionBar}>
          <TouchableOpacity
            style={[styles.chatActionBtn, { backgroundColor: borderColor }]}
            onPress={() => onInitiateChat(persona)}
            activeOpacity={0.85}
          >
            <MessageIcon size={16} color="#FFFFFF" />
            <Text style={styles.chatActionBtnText}>Chat with {persona.name}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#16161D',
  },
  closeBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#161620',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#262634',
  },
  topBarTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 17,
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  topBarRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerActionBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#161620',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#262634',
  },
  deleteHeaderBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.25)',
  },
  scrollBody: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 40,
    gap: 20,
  },
  heroSection: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  avatarFrame: {
    width: 110,
    height: 110,
    borderRadius: 30,
    borderWidth: 3,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    ...Platform.select({
      android: { elevation: 8 },
      ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.4, shadowRadius: 10 },
    }),
  },
  avatarImage: {
    width: '100%',
    height: '100%',
  },
  avatarFallback: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 48,
  },
  heroName: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 26,
    color: '#FFFFFF',
    letterSpacing: 0.4,
    textAlign: 'center',
  },
  heroTagline: {
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
    marginTop: 6,
    paddingHorizontal: 16,
    lineHeight: 20,
  },
  badgesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 14,
    flexWrap: 'wrap',
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 9,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  neutralBadge: {
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 9,
    backgroundColor: '#121218',
    borderWidth: 1,
    borderColor: '#22222E',
  },
  neutralBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  sectionCard: {
    backgroundColor: '#0D0D14',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#1F1F2C',
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#9CA3AF',
    letterSpacing: 0.6,
  },
  dialogueBox: {
    backgroundColor: '#14141E',
    borderRadius: 12,
    borderLeftWidth: 3.5,
    padding: 14,
  },
  dialogueText: {
    fontSize: 14,
    lineHeight: 22,
    color: '#F3F4F6',
  },
  memoryBox: {
    backgroundColor: '#14141E',
    borderRadius: 12,
    padding: 14,
  },
  memoryText: {
    fontSize: 13.5,
    lineHeight: 21,
    color: '#D1D5DB',
  },
  emptyFieldText: {
    fontSize: 13,
    color: '#6B7280',
    fontStyle: 'italic',
  },
  specsCard: {
    backgroundColor: '#09090D',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#191924',
    padding: 16,
  },
  specsTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 13,
    color: '#6B7280',
    letterSpacing: 0.5,
    marginBottom: 14,
  },
  specRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  specDivider: {
    height: 1,
    backgroundColor: '#161622',
    marginVertical: 10,
  },
  specKey: {
    fontSize: 13,
    color: '#9CA3AF',
  },
  specValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E5E7EB',
  },
  colorIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  colorDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  actionBar: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 16,
    borderTopWidth: 1,
    borderTopColor: '#16161D',
    backgroundColor: '#000000',
  },
  chatActionBtn: {
    flexDirection: 'row',
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  chatActionBtnText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    color: '#FFFFFF',
    letterSpacing: 0.4,
  },
});
