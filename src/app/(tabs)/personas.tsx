import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Image,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import Svg, { Path, Circle } from 'react-native-svg';
import { useAuth } from '../../context/AuthContext';
import { theme } from '../../constants/theme';
import MarkdownText from '../../components/MarkdownText';
import { showAlert } from '../../context/AlertContext';
import PersonaDetailModal from '../../components/PersonaDetailModal';
import CompanionChatModal from '../../components/CompanionChatModal';
import {
  PersonaItem,
  getStoredPersonas,
  fetchAndSyncPersonas,
  deletePersonaFromRoster,
  subscribePersonas,
} from '../../services/personaService';

function ShieldLockIcon({ size = 13, color = '#F43F5E' }: { size?: number; color?: string }) {
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

function GlobeIcon({ size = 13, color = '#10B981' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth="2" />
      <Path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" stroke={color} strokeWidth="1.8" />
    </Svg>
  );
}

function TrashIcon({ size = 16, color = '#6B7280' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M10 11v6M14 11v6" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </Svg>
  );
}

function MessageIcon({ size = 15, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill={color} />
    </Svg>
  );
}

export default function PersonasScreen() {
  const { user } = useAuth();
  const [personas, setPersonas] = useState<PersonaItem[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<PersonaItem | null>(null);
  const [activeChatPersona, setActiveChatPersona] = useState<PersonaItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [activeFilter, setActiveFilter] = useState<'all' | 'private' | 'public'>('all');

  const handleInitiateChat = (p: PersonaItem) => {
    setActiveChatPersona(p);
  };

  const loadPersonas = useCallback(async (isPullToRefresh = false) => {
    if (isPullToRefresh) {
      setRefreshing(true);
    }
    try {
      // 1. Initial quick load from local cache scoped to current user ID
      if (!isPullToRefresh) {
        const cached = await getStoredPersonas(user?.id);
        if (cached && cached.length > 0) {
          setPersonas(cached);
          setLoading(false);
        }
      }
      // 2. Fetch directly from PostgreSQL database for current logged in user ID
      const synced = await fetchAndSyncPersonas(user?.id);
      setPersonas(synced);
    } catch (err) {
      console.warn('[Personas] Error loading personas:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.id]);

  // Subscribe to real-time events across the app (creation, deletion, syncing)
  useEffect(() => {
    const unsubscribe = subscribePersonas((updated) => {
      setPersonas(updated);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  // Automatically refresh whenever this tab comes into focus or user ID resolves
  useEffect(() => {
    if (user?.id) {
      loadPersonas(false);
    }
  }, [user?.id, loadPersonas]);

  useFocusEffect(
    useCallback(() => {
      loadPersonas(false);
    }, [loadPersonas])
  );

  const onRefresh = useCallback(() => {
    loadPersonas(true);
  }, [loadPersonas]);

  const handleDelete = (id: string, name: string) => {
    showAlert(
      'Delete Persona',
      `Are you sure you want to remove "${name}" from your roster?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            // Instant 0ms optimistic UI update: card vanishes immediately
            setPersonas((prev) => prev.filter((p) => p.id !== id));
            deletePersonaFromRoster(id, user?.id);
          },
        },
      ],
      'danger'
    );
  };

  const filteredPersonas = personas.filter((p) => {
    if (activeFilter === 'all') return true;
    return p.visibility === activeFilter;
  });

  const renderPersonaCard = ({ item }: { item: PersonaItem }) => {
    const borderColor = item.border_color || '#F43F5E';
    const isPrivate = item.visibility === 'private';

    return (
      <TouchableOpacity
        style={[styles.card, { borderColor: '#1F2937' }]}
        onPress={() => setSelectedPersona(item)}
        activeOpacity={0.88}
      >
        {/* Header row: Portrait + Info + Delete */}
        <View style={styles.cardHeader}>
          {/* Avatar Portrait with dynamic border color */}
          <View style={[styles.avatarFrame, { borderColor }]}>
            {item.image_url ? (
              <Image source={{ uri: item.image_url }} style={styles.avatarImage} />
            ) : (
              <View style={[styles.avatarFallback, { backgroundColor: borderColor + '20' }]}>
                <Text style={[styles.avatarInitial, { color: borderColor }]}>
                  {item.name ? item.name.charAt(0).toUpperCase() : 'A'}
                </Text>
              </View>
            )}
          </View>

          {/* Identity details */}
          <View style={styles.cardInfo}>
            <View style={styles.nameRow}>
              <Text style={styles.cardName} numberOfLines={1}>
                {item.name}{item.age ? `, ${item.age}` : ''}
              </Text>
              {/* Visibility badge */}
              <View
                style={[
                  styles.visibilityBadge,
                  {
                    backgroundColor: isPrivate ? 'rgba(244, 63, 94, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                    borderColor: isPrivate ? 'rgba(244, 63, 94, 0.3)' : 'rgba(16, 185, 129, 0.3)',
                  },
                ]}
              >
                {isPrivate ? <ShieldLockIcon size={11} color="#F43F5E" /> : <GlobeIcon size={11} color="#10B981" />}
                <Text
                  style={[
                    styles.visibilityText,
                    { color: isPrivate ? '#F43F5E' : '#10B981' },
                  ]}
                >
                  {isPrivate ? 'Private' : 'Community'}
                </Text>
              </View>
            </View>

            {item.tagline ? (
              <Text style={styles.cardTagline} numberOfLines={2}>
                {item.tagline}
              </Text>
            ) : null}
          </View>

          {/* Delete Action */}
          <TouchableOpacity
            style={styles.deleteBtn}
            onPress={(e) => {
              e.stopPropagation();
              handleDelete(item.id, item.name);
            }}
            activeOpacity={0.7}
            accessibilityLabel={`Delete ${item.name}`}
          >
            <TrashIcon size={15} color="#4B5563" />
          </TouchableOpacity>
        </View>

        {/* Roleplay Opening Greeting Preview */}
        {item.greeting ? (
          <View style={styles.greetingBox}>
            <Text style={styles.greetingLabel}>First Message</Text>
            <MarkdownText content={item.greeting} style={styles.greetingText} />
          </View>
        ) : null}

        {/* Action Bar */}
        <View style={styles.cardActions}>
          <TouchableOpacity
            style={styles.detailsBtn}
            onPress={() => setSelectedPersona(item)}
            activeOpacity={0.8}
          >
            <Text style={styles.detailsBtnText}>View Profile</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.chatBtn, { backgroundColor: borderColor }]}
            onPress={() => handleInitiateChat(item)}
            activeOpacity={0.85}
          >
            <MessageIcon size={14} color="#FFFFFF" />
            <Text style={styles.chatBtnText}>Chat Now</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Top Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <Text style={styles.headerTitle}>MY PERSONAS</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countText}>{personas.length}</Text>
          </View>
        </View>
        <Text style={styles.headerSubtitle}>
          Your companions ready to chat
        </Text>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterBar}>
        <TouchableOpacity
          style={[styles.filterChip, activeFilter === 'all' && styles.filterChipActive]}
          onPress={() => setActiveFilter('all')}
          activeOpacity={0.8}
        >
          <Text style={[styles.filterChipText, activeFilter === 'all' && styles.filterChipTextActive]}>
            All ({personas.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.filterChip, activeFilter === 'private' && styles.filterChipActive]}
          onPress={() => setActiveFilter('private')}
          activeOpacity={0.8}
        >
          <Text style={[styles.filterChipText, activeFilter === 'private' && styles.filterChipTextActive]}>
            Private
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.filterChip, activeFilter === 'public' && styles.filterChipActive]}
          onPress={() => setActiveFilter('public')}
          activeOpacity={0.8}
        >
          <Text style={[styles.filterChipText, activeFilter === 'public' && styles.filterChipTextActive]}>
            Community
          </Text>
        </TouchableOpacity>
      </View>

      {/* Main Content */}
      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#F43F5E" />
          <Text style={styles.loadingText}>Loading your personas...</Text>
        </View>
      ) : filteredPersonas.length === 0 ? (
        <View style={styles.emptyContainer}>
          <View style={styles.emptyIconCircle}>
            <ShieldLockIcon size={32} color="#6B7280" />
          </View>
          <Text style={styles.emptyTitle}>No Personas Yet</Text>
          <Text style={styles.emptySubtitle}>
            Create your first companion with their own voice and personality.
          </Text>
          <TouchableOpacity
            style={styles.forgeBtn}
            onPress={() => router.push('/(tabs)/create')}
            activeOpacity={0.85}
          >
            <Text style={styles.forgeBtnText}>Create Persona</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={filteredPersonas}
          keyExtractor={(item) => item.id}
          renderItem={renderPersonaCard}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#F43F5E"
              colors={['#F43F5E']}
            />
          }
        />
      )}

      {/* Comprehensive Avatar Profile & Memory Detail Modal */}
      <PersonaDetailModal
        visible={!!selectedPersona}
        persona={selectedPersona}
        onClose={() => setSelectedPersona(null)}
        onInitiateChat={(p) => {
          setSelectedPersona(null);
          handleInitiateChat(p);
        }}
        onDelete={handleDelete}
      />

      {/* Real Interactive Chat Modal */}
      <CompanionChatModal
        visible={!!activeChatPersona}
        persona={activeChatPersona}
        onClose={() => setActiveChatPersona(null)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#16161A',
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 22,
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  countBadge: {
    backgroundColor: '#1E1E24',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#2E2E38',
  },
  countText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
    color: '#F43F5E',
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    marginTop: 4,
  },
  filterBar: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingVertical: 12,
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: '#111116',
    borderWidth: 1,
    borderColor: '#1F2937',
  },
  filterChipActive: {
    backgroundColor: '#26141A',
    borderColor: '#F43F5E',
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  filterChipTextActive: {
    color: '#F43F5E',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    gap: 14,
  },
  card: {
    backgroundColor: '#0D0D12',
    borderRadius: 18,
    borderWidth: 1,
    padding: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  avatarFrame: {
    width: 64,
    height: 64,
    borderRadius: 16,
    borderWidth: 2.5,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarImage: {
    width: '100%',
    height: '100%',
    borderRadius: 13,
  },
  avatarFallback: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 26,
  },
  cardInfo: {
    flex: 1,
    justifyContent: 'center',
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  cardName: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 17,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  visibilityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 8,
    borderWidth: 1,
  },
  visibilityText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  cardTagline: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 3,
    lineHeight: 17,
  },
  deleteBtn: {
    padding: 6,
    borderRadius: 8,
  },
  greetingBox: {
    backgroundColor: '#14141B',
    borderRadius: 12,
    padding: 12,
    marginTop: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#F43F5E',
  },
  greetingLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#6B7280',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  greetingText: {
    fontSize: 13,
    lineHeight: 19,
    color: '#E5E7EB',
  },
  cardActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 14,
    gap: 8,
  },
  detailsBtn: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 10,
    backgroundColor: '#161622',
    borderWidth: 1,
    borderColor: '#262638',
    alignItems: 'center',
    justifyContent: 'center',
  },
  detailsBtnText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 13,
    color: '#9CA3AF',
    letterSpacing: 0.3,
  },
  chatBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 18,
    paddingVertical: 9,
    borderRadius: 10,
  },
  chatBtnText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 13,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 13,
    color: '#9CA3AF',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 12,
  },
  emptyIconCircle: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: '#14141B',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  emptyTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 19,
    color: '#FFFFFF',
  },
  emptySubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 19,
  },
  forgeBtn: {
    marginTop: 10,
    backgroundColor: '#F43F5E',
    paddingHorizontal: 22,
    paddingVertical: 11,
    borderRadius: 12,
  },
  forgeBtnText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 14,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
});
