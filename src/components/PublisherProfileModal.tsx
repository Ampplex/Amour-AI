import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  ScrollView,
  TouchableOpacity,
  Image,
  Dimensions,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { FeedPersonaItem, togglePublisherFollow } from '../services/feedService';
import { PersonaItem } from '../services/personaService';
import { API_CONFIG } from '../constants/authConfig';

const { width } = Dimensions.get('window');

interface PublisherProfileData {
  name: string;
  handle: string;
  avatar: string;
  followers_count: number;
  personas_count: number;
  is_following: boolean;
  personas: PersonaItem[];
}

interface PublisherProfileModalProps {
  visible: boolean;
  publisherHandle: string | null;
  initialPublisherName?: string;
  initialPublisherAvatar?: string;
  userId?: string;
  onClose: () => void;
  onSelectPersona: (persona: PersonaItem) => void;
  onToggleFollowParent?: (handle: string, currentFollowing: boolean) => void;
}

function CloseIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function MessageIcon({ size = 14, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </Svg>
  );
}

const CANDIDATE_URLS = [
  API_CONFIG.baseUrl,
  'http://192.168.1.4:8000/api',
  'http://10.104.217.217:8000/api',
  'http://192.168.1.2:8000/api',
];

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 2500): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return res;
  } catch (e) {
    clearTimeout(id);
    throw e;
  }
}

async function fetchPublisherProfile(identifier: string, userId?: string): Promise<PublisherProfileData | null> {
  const clean = encodeURIComponent(identifier.trim());
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  for (const base of CANDIDATE_URLS) {
    try {
      const res = await fetchWithTimeout(`${base}/memory/publishers/${clean}/profile/${query}`, {}, 2500);
      if (res.ok) {
        return await res.json();
      }
    } catch {}
  }
  return null;
}

export default function PublisherProfileModal({
  visible,
  publisherHandle,
  initialPublisherName,
  initialPublisherAvatar,
  userId,
  onClose,
  onSelectPersona,
  onToggleFollowParent,
}: PublisherProfileModalProps) {
  const [profile, setProfile] = useState<PublisherProfileData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isFollowing, setIsFollowing] = useState<boolean>(false);
  const [followersCount, setFollowersCount] = useState<number>(0);

  useEffect(() => {
    if (!visible || !publisherHandle) return;

    setLoading(true);
    fetchPublisherProfile(publisherHandle, userId)
      .then((data) => {
        if (data) {
          setProfile(data);
          setIsFollowing(data.is_following);
          setFollowersCount(data.followers_count);
        } else {
          setProfile({
            name: initialPublisherName || 'Creator',
            handle: publisherHandle,
            avatar: initialPublisherAvatar || '',
            followers_count: 0,
            personas_count: 0,
            is_following: false,
            personas: [],
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [visible, publisherHandle, initialPublisherName, initialPublisherAvatar, userId]);

  const handleFollowToggle = async () => {
    if (!publisherHandle) return;
    const nextState = !isFollowing;
    setIsFollowing(nextState);
    setFollowersCount((prev) => Math.max(0, prev + (nextState ? 1 : -1)));

    if (onToggleFollowParent) {
      onToggleFollowParent(publisherHandle, isFollowing);
    }
    await togglePublisherFollow(publisherHandle, isFollowing, userId);
  };

  if (!visible) return null;

  const displayName = profile?.name || initialPublisherName || 'Creator';
  const displayHandle = profile?.handle || publisherHandle || '@creator';
  const displayAvatar = profile?.avatar || initialPublisherAvatar || '';

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        {/* Top Header */}
        <View style={styles.topBar}>
          <TouchableOpacity
            style={styles.closeBtn}
            onPress={onClose}
            activeOpacity={0.7}
            accessibilityLabel="Close publisher profile"
          >
            <CloseIcon size={18} color="#FFFFFF" />
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>CREATOR PROFILE</Text>
          <View style={{ width: 36 }} />
        </View>

        <ScrollView
          style={styles.scrollBody}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Creator Hero Header */}
          <View style={styles.creatorHeroCard}>
            <View style={styles.avatarBorderFrame}>
              {displayAvatar ? (
                <Image source={{ uri: displayAvatar }} style={styles.avatarLargeImg} />
              ) : (
                <View style={styles.avatarFallbackCircle}>
                  <Text style={styles.avatarFallbackLetter}>
                    {displayName.charAt(0).toUpperCase()}
                  </Text>
                </View>
              )}
            </View>

            <Text style={styles.creatorNameText}>{displayName}</Text>
            <Text style={styles.creatorHandleText}>{displayHandle}</Text>

            {/* Stats Row */}
            <View style={styles.statsRow}>
              <View style={styles.statCol}>
                <Text style={styles.statNumberText}>{profile?.personas?.length || 0}</Text>
                <Text style={styles.statLabelText}>Companions</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statCol}>
                <Text style={styles.statNumberText}>{followersCount}</Text>
                <Text style={styles.statLabelText}>Followers</Text>
              </View>
            </View>

            {/* Follow / Unfollow Button */}
            <TouchableOpacity
              style={[
                styles.followActionButton,
                isFollowing ? styles.followingActiveButton : styles.followDefaultButton,
              ]}
              onPress={handleFollowToggle}
              activeOpacity={0.8}
            >
              <Text style={[styles.followActionText, isFollowing && styles.followingActiveText]}>
                {isFollowing ? 'Following' : 'Follow Creator'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Section: Published Companions */}
          <View style={styles.companionsSectionHeader}>
            <Text style={styles.sectionHeaderTitle}>PUBLISHED COMPANIONS</Text>
            <Text style={styles.sectionHeaderSubtitle}>
              Original avatars forged by {displayName}
            </Text>
          </View>

          {loading ? (
            <View style={styles.centerLoading}>
              <ActivityIndicator size="small" color="#F43F5E" />
            </View>
          ) : !profile?.personas || profile.personas.length === 0 ? (
            <View style={styles.emptyCompanionsBox}>
              <Text style={styles.emptyCompanionsText}>No public companions published yet.</Text>
            </View>
          ) : (
            <View style={styles.companionsList}>
              {profile.personas.map((persona) => {
                const accent = persona.border_color || '#F43F5E';
                return (
                  <TouchableOpacity
                    key={persona.id}
                    style={styles.personaCardRow}
                    onPress={() => {
                      onClose();
                      setTimeout(() => {
                        onSelectPersona(persona);
                      }, 150);
                    }}
                    activeOpacity={0.85}
                  >
                    <View style={[styles.personaMiniSquircle, { borderColor: accent }]}>
                      {persona.image_url ? (
                        <Image source={{ uri: persona.image_url }} style={styles.personaMiniImg} />
                      ) : (
                        <View style={[styles.personaMiniFallback, { backgroundColor: accent + '20' }]}>
                          <Text style={[styles.personaMiniInitial, { color: accent }]}>
                            {persona.name.charAt(0).toUpperCase()}
                          </Text>
                        </View>
                      )}
                    </View>

                    <View style={styles.personaInfoCol}>
                      <Text style={styles.personaNameText}>{persona.name}</Text>
                      {persona.tagline ? (
                        <Text style={styles.personaTaglineText} numberOfLines={1}>
                          {persona.tagline}
                        </Text>
                      ) : null}
                      {persona.greeting ? (
                        <Text style={styles.personaGreetingPreview} numberOfLines={1}>
                          {persona.greeting}
                        </Text>
                      ) : null}
                    </View>

                    <View style={[styles.viewProfilePill, { borderColor: accent }]}>
                      <MessageIcon size={12} color={accent} />
                      <Text style={[styles.viewProfilePillText, { color: accent }]}>View</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#09090D',
  },
  topBar: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#161622',
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#161622',
    alignItems: 'center',
    justifyContent: 'center',
  },
  topBarTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    letterSpacing: 1,
  },
  scrollBody: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 40,
  },

  // Creator Hero Card
  creatorHeroCard: {
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 20,
    backgroundColor: '#0D0D14',
    borderBottomWidth: 1,
    borderBottomColor: '#161622',
  },
  avatarBorderFrame: {
    width: 90,
    height: 90,
    borderRadius: 45,
    borderWidth: 2,
    borderColor: '#F43F5E',
    overflow: 'hidden',
    backgroundColor: '#1E1E2A',
    marginBottom: 12,
  },
  avatarLargeImg: {
    width: '100%',
    height: '100%',
  },
  avatarFallbackCircle: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1F1F2E',
  },
  avatarFallbackLetter: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: '700',
  },
  creatorNameText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
    letterSpacing: 0.5,
  },
  creatorHandleText: {
    color: '#9CA3AF',
    fontSize: 13,
    marginTop: 2,
  },

  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 18,
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: '#13131D',
    borderWidth: 1,
    borderColor: '#1F1F2E',
    gap: 28,
  },
  statCol: {
    alignItems: 'center',
  },
  statNumberText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 16,
  },
  statLabelText: {
    color: '#9CA3AF',
    fontSize: 11,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 24,
    backgroundColor: '#262638',
  },

  followActionButton: {
    paddingHorizontal: 32,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  followDefaultButton: {
    borderColor: '#F43F5E',
    backgroundColor: '#F43F5E',
  },
  followingActiveButton: {
    borderColor: '#374151',
    backgroundColor: '#1F2937',
  },
  followActionText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  followingActiveText: {
    color: '#9CA3AF',
  },

  // Published Companions
  companionsSectionHeader: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 10,
  },
  sectionHeaderTitle: {
    color: '#9CA3AF',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
  },
  sectionHeaderSubtitle: {
    color: '#6B7280',
    fontSize: 12,
    marginTop: 2,
  },
  centerLoading: {
    paddingVertical: 30,
    alignItems: 'center',
  },
  emptyCompanionsBox: {
    paddingVertical: 24,
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  emptyCompanionsText: {
    color: '#6B7280',
    fontSize: 13,
  },

  companionsList: {
    paddingHorizontal: 16,
    gap: 10,
  },
  personaCardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 14,
    backgroundColor: '#13131D',
    borderWidth: 1,
    borderColor: '#1E1E2C',
    gap: 12,
  },
  personaMiniSquircle: {
    width: 48,
    height: 48,
    borderRadius: 14,
    borderWidth: 1.5,
    overflow: 'hidden',
    backgroundColor: '#1E1E2A',
  },
  personaMiniImg: {
    width: '100%',
    height: '100%',
  },
  personaMiniFallback: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  personaMiniInitial: {
    fontSize: 18,
    fontWeight: '700',
  },
  personaInfoCol: {
    flex: 1,
  },
  personaNameText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  personaTaglineText: {
    color: '#9CA3AF',
    fontSize: 11,
    marginTop: 1,
  },
  personaGreetingPreview: {
    color: '#6B7280',
    fontSize: 11,
    fontStyle: 'italic',
    marginTop: 2,
  },
  viewProfilePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 10,
    borderWidth: 1,
  },
  viewProfilePillText: {
    fontWeight: '600',
    fontSize: 11,
  },
});
