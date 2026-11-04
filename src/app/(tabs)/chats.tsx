import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  Image,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import Svg, { Path } from 'react-native-svg';
import { useAuth } from '../../context/AuthContext';
import CompanionChatModal from '../../components/CompanionChatModal';
import { PersonaItem } from '../../services/personaService';
import {
  fetchUserConversations,
  ConversationItem,
} from '../../services/conversationService';

function MessageBubbleIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function EmptyChatIcon({ size = 56, color = '#374151' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 0 1-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function formatRelativeTime(dateString: string): string {
  if (!dateString) return '';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '';

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m`;
  if (diffHours < 24) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) {
    return date.toLocaleDateString([], { weekday: 'short' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export default function ChatsScreen() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [activeChatPersona, setActiveChatPersona] = useState<PersonaItem | null>(null);

  const loadConversations = useCallback(
    async (isPullToRefresh = false) => {
      if (!user?.id) {
        setConversations([]);
        setLoading(false);
        setRefreshing(false);
        return;
      }

      if (isPullToRefresh) {
        setRefreshing(true);
      }

      try {
        const data = await fetchUserConversations(user.id, user.token);
        setConversations(data);
      } catch (err) {
        console.warn('[ChatsScreen] Error loading conversations:', err);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [user?.id, user?.token]
  );

  useEffect(() => {
    loadConversations(false);
  }, [loadConversations]);

  useFocusEffect(
    useCallback(() => {
      loadConversations(false);
    }, [loadConversations])
  );

  const onRefresh = useCallback(() => {
    loadConversations(true);
  }, [loadConversations]);

  const handleOpenChat = (persona: PersonaItem) => {
    setActiveChatPersona(persona);
  };

  const renderConversationItem = ({ item }: { item: ConversationItem }) => {
    const { persona, last_message } = item;
    const isUserLast = last_message?.sender === 'user';
    const messagePreview = isUserLast
      ? `You: ${last_message?.text || ''}`
      : last_message?.text || '';
    const formattedTime = formatRelativeTime(last_message?.created_at);

    return (
      <TouchableOpacity
        style={styles.chatCard}
        onPress={() => handleOpenChat(persona)}
        activeOpacity={0.7}
      >
        <View style={[styles.avatarContainer, { borderColor: persona.border_color || '#F43F5E' }]}>
          {persona.image_url ? (
            <Image source={{ uri: persona.image_url }} style={styles.avatarImage} />
          ) : (
            <View style={styles.avatarPlaceholder}>
              <Text style={styles.avatarInitial}>
                {persona.name ? persona.name.charAt(0).toUpperCase() : 'C'}
              </Text>
            </View>
          )}
        </View>

        <View style={styles.chatInfoContainer}>
          <View style={styles.chatTopRow}>
            <Text style={styles.personaName} numberOfLines={1}>
              {persona.name}
            </Text>
            {formattedTime ? <Text style={styles.timeText}>{formattedTime}</Text> : null}
          </View>

          {persona.tagline ? (
            <Text style={styles.taglineText} numberOfLines={1}>
              {persona.tagline}
            </Text>
          ) : null}

          <Text
            style={[styles.lastMessageText, isUserLast && styles.lastMessageUserText]}
            numberOfLines={1}
            ellipsizeMode="tail"
          >
            {messagePreview || 'Start a conversation...'}
          </Text>
        </View>

        <Text style={styles.chevron}>›</Text>
      </TouchableOpacity>
    );
  };

  if (!user) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Chats</Text>
        </View>
        <View style={styles.guestContainer}>
          <EmptyChatIcon size={56} color="#4B5563" />
          <Text style={styles.guestTitle}>Your Conversations</Text>
          <Text style={styles.guestSubtitle}>
            Sign in to view your persona chat threads, real-time replies, and long-term memories.
          </Text>
          <TouchableOpacity
            style={styles.signInButton}
            onPress={() => router.push('/login')}
            activeOpacity={0.8}
          >
            <Text style={styles.signInButtonText}>Sign In</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <Text style={styles.headerTitle}>CHATS</Text>
          {conversations.length > 0 ? (
            <View style={styles.countBadge}>
              <Text style={styles.countBadgeText}>{conversations.length}</Text>
            </View>
          ) : null}
        </View>
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#F43F5E" />
        </View>
      ) : conversations.length === 0 ? (
        <FlatList
          data={[]}
          renderItem={() => null}
          contentContainerStyle={styles.emptyScrollContainer}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#F43F5E"
              colors={['#F43F5E']}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconCircle}>
                <EmptyChatIcon size={46} color="#6B7280" />
              </View>
              <Text style={styles.emptyTitle}>No Conversations Yet</Text>
              <Text style={styles.emptySubtitle}>
                Start chatting with any AI persona from Home or Explore to see your dialogue threads here.
              </Text>
              <TouchableOpacity
                style={styles.exploreButton}
                onPress={() => router.push('/personas')}
                activeOpacity={0.8}
              >
                <Text style={styles.exploreButtonText}>Explore Personas</Text>
              </TouchableOpacity>
            </View>
          }
        />
      ) : (
        <FlatList
          data={conversations}
          keyExtractor={(item) => item.persona.id}
          renderItem={renderConversationItem}
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

      {activeChatPersona && (
        <CompanionChatModal
          visible={!!activeChatPersona}
          persona={activeChatPersona}
          onClose={() => {
            setActiveChatPersona(null);
            loadConversations(false);
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#000000',
  },
  header: {
    paddingHorizontal: 18,
    paddingTop: 10,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#16161E',
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 24,
    letterSpacing: 0.5,
  },
  countBadge: {
    backgroundColor: '#1E1E2A',
    borderColor: '#2D2D3D',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  countBadgeText: {
    color: '#F43F5E',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  listContent: {
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 24,
  },
  chatCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0F0F14',
    borderColor: '#1C1C26',
    borderWidth: 1,
    borderRadius: 16,
    padding: 12,
    marginBottom: 10,
  },
  avatarContainer: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: 2,
    overflow: 'hidden',
    backgroundColor: '#181822',
  },
  avatarImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  avatarPlaceholder: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C28',
  },
  avatarInitial: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
  },
  chatInfoContainer: {
    flex: 1,
    marginLeft: 12,
    marginRight: 6,
  },
  chatTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  personaName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    flex: 1,
    marginRight: 8,
  },
  timeText: {
    color: '#6B7280',
    fontSize: 12,
  },
  taglineText: {
    color: '#9CA3AF',
    fontSize: 12,
    marginBottom: 3,
  },
  lastMessageText: {
    color: '#6B7280',
    fontSize: 13,
    lineHeight: 18,
  },
  lastMessageUserText: {
    color: '#9CA3AF',
  },
  chevron: {
    color: '#4B5563',
    fontSize: 20,
    fontWeight: '300',
    marginLeft: 4,
  },
  emptyScrollContainer: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    paddingVertical: 60,
  },
  emptyIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#121218',
    borderColor: '#20202C',
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
  },
  emptyTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
    marginBottom: 8,
    textAlign: 'center',
  },
  emptySubtitle: {
    color: '#6B7280',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 22,
  },
  exploreButton: {
    backgroundColor: '#1A1A24',
    borderColor: '#F43F5E',
    borderWidth: 1,
    paddingHorizontal: 22,
    paddingVertical: 12,
    borderRadius: 24,
  },
  exploreButtonText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 14,
  },
  guestContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  guestTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
    marginTop: 18,
    marginBottom: 8,
    textAlign: 'center',
  },
  guestSubtitle: {
    color: '#6B7280',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  signInButton: {
    backgroundColor: '#F43F5E',
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 24,
  },
  signInButtonText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 15,
  },
});
