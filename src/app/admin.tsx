import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  TextInput,
  FlatList,
  Modal,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Switch,
  Alert,
  Clipboard,
  Platform,
  Image,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Circle, Rect } from 'react-native-svg';
import { router } from 'expo-router';
import { useAuth } from '../context/AuthContext';
import {
  AdminUserAccount,
  AdminUserStats,
  AdminUserFilterParams,
  fetchAdminUsers,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
} from '../services/adminService';

// --- Icons ---
function BackIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M15 18L9 12L15 6" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function RefreshIcon({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M23 4v6h-6M1 20v-6h6"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function ShieldIcon({ size = 20, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function SearchIcon({ size = 16, color = '#71717A' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="11" cy="11" r="8" stroke={color} strokeWidth="2" />
      <Path d="M21 21l-4.35-4.35" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </Svg>
  );
}

function PlusIcon({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 5v14M5 12h14" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function CloseIcon({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function CopyIcon({ size = 14, color = '#A1A1AA' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke={color} strokeWidth="2" />
      <Path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export default function AdminConsoleScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [users, setUsers] = useState<AdminUserAccount[]>([]);
  const [stats, setStats] = useState<AdminUserStats>({
    total_users: 0,
    active_users: 0,
    verified_users: 0,
    staff_users: 0,
    google_users: 0,
    local_users: 0,
  });

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive' | 'google' | 'local' | 'staff' | 'unverified'>('all');

  // Modals
  const [inspectUser, setInspectUser] = useState<AdminUserAccount | null>(null);
  const [editUser, setEditUser] = useState<AdminUserAccount | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [userToDelete, setUserToDelete] = useState<AdminUserAccount | null>(null);

  // Form states (Create / Edit)
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    name: '',
    given_name: '',
    family_name: '',
    password: '',
    picture: '',
    auth_provider: 'local',
    is_active: true,
    verified_email: true,
    is_staff: false,
    is_superuser: false,
  });
  const [formSaving, setFormSaving] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Load Users from Backend
  const loadUsers = useCallback(async (isPull = false) => {
    if (isPull) setRefreshing(true);
    else setLoading(true);

    try {
      const filters: AdminUserFilterParams = {
        search: searchQuery.trim() || undefined,
      };

      if (activeFilter === 'active') filters.is_active = 'true';
      if (activeFilter === 'inactive') filters.is_active = 'false';
      if (activeFilter === 'google') filters.auth_provider = 'google';
      if (activeFilter === 'local') filters.auth_provider = 'local';
      if (activeFilter === 'staff') filters.is_staff = 'true';
      if (activeFilter === 'unverified') filters.verified_email = 'false';

      const res = await fetchAdminUsers(filters, user?.id);
      setUsers(res.users);
      setStats(res.stats);
    } catch (err: any) {
      console.warn('[AdminConsole] Load error:', err);
      Alert.alert('Admin Console Notice', err.message || 'Failed to load user accounts.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [searchQuery, activeFilter, user?.id]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Copy helper
  const handleCopy = (text: string, label: string) => {
    Clipboard.setString(text);
    setCopiedKey(label);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Quick Toggle Active Status
  const handleQuickToggleActive = async (targetUser: AdminUserAccount) => {
    const nextStatus = !targetUser.is_active;
    try {
      const updated = await updateAdminUser(targetUser.id, { is_active: nextStatus }, user?.id);
      setUsers((prev) => prev.map((u) => (u.id === targetUser.id ? updated : u)));
    } catch (err: any) {
      Alert.alert('Update Failed', err.message || 'Could not update user status.');
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (targetUser: AdminUserAccount) => {
    setEditUser(targetUser);
    setFormData({
      email: targetUser.email,
      username: targetUser.username || '',
      name: targetUser.name || '',
      given_name: targetUser.given_name || '',
      family_name: targetUser.family_name || '',
      password: '',
      picture: targetUser.picture || '',
      auth_provider: targetUser.auth_provider || 'local',
      is_active: targetUser.is_active,
      verified_email: targetUser.verified_email,
      is_staff: targetUser.is_staff,
      is_superuser: targetUser.is_superuser,
    });
    setFormError(null);
  };

  // Save Edit
  const handleSaveEdit = async () => {
    if (!editUser) return;
    setFormSaving(true);
    setFormError(null);

    try {
      const payload: any = {
        email: formData.email.trim(),
        username: formData.username.trim() || null,
        name: formData.name.trim(),
        given_name: formData.given_name.trim(),
        family_name: formData.family_name.trim(),
        picture: formData.picture.trim(),
        auth_provider: formData.auth_provider,
        is_active: formData.is_active,
        verified_email: formData.verified_email,
        is_staff: formData.is_staff,
        is_superuser: formData.is_superuser,
      };

      if (formData.password.trim()) {
        payload.password = formData.password.trim();
      }

      const updated = await updateAdminUser(editUser.id, payload, user?.id);
      setUsers((prev) => prev.map((u) => (u.id === editUser.id ? updated : u)));
      setEditUser(null);
    } catch (err: any) {
      setFormError(err.message || 'Failed to update user account.');
    } finally {
      setFormSaving(false);
    }
  };

  // Open Create Modal
  const handleOpenCreate = () => {
    setFormData({
      email: '',
      username: '',
      name: '',
      given_name: '',
      family_name: '',
      password: '',
      picture: '',
      auth_provider: 'local',
      is_active: true,
      verified_email: true,
      is_staff: false,
      is_superuser: false,
    });
    setFormError(null);
    setIsCreateModalOpen(true);
  };

  // Save Create
  const handleSaveCreate = async () => {
    if (!formData.email.trim()) {
      setFormError('Email is required');
      return;
    }
    setFormSaving(true);
    setFormError(null);

    try {
      const created = await createAdminUser(formData, user?.id);
      setUsers((prev) => [created, ...prev]);
      setIsCreateModalOpen(false);
      loadUsers();
    } catch (err: any) {
      setFormError(err.message || 'Failed to create user account.');
    } finally {
      setFormSaving(false);
    }
  };

  // Execute Delete
  const handleConfirmDelete = async () => {
    if (!userToDelete) return;
    try {
      await deleteAdminUser(userToDelete.id, user?.id);
      setUsers((prev) => prev.filter((u) => u.id !== userToDelete.id));
      setUserToDelete(null);
      loadUsers();
    } catch (err: any) {
      Alert.alert('Delete Failed', err.message || 'Could not delete user account.');
    }
  };

  // Render Stats Header
  const renderStatsHeader = () => (
    <View style={styles.statsContainer}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsScroll}>
        <View style={[styles.statTile, { borderColor: '#F43F5E33' }]}>
          <Text style={styles.statLabel}>Total Users</Text>
          <Text style={[styles.statValue, { color: '#F43F5E' }]}>{stats.total_users}</Text>
          <Text style={styles.statSub}>Neon PostgreSQL</Text>
        </View>

        <View style={[styles.statTile, { borderColor: '#10B98133' }]}>
          <Text style={styles.statLabel}>Active</Text>
          <Text style={[styles.statValue, { color: '#10B981' }]}>{stats.active_users}</Text>
          <Text style={styles.statSub}>Allowed Access</Text>
        </View>

        <View style={[styles.statTile, { borderColor: '#3B82F633' }]}>
          <Text style={styles.statLabel}>Google Auth</Text>
          <Text style={[styles.statValue, { color: '#60A5FA' }]}>{stats.google_users}</Text>
          <Text style={styles.statSub}>OAuth 2.0</Text>
        </View>

        <View style={[styles.statTile, { borderColor: '#A855F733' }]}>
          <Text style={styles.statLabel}>Staff / Admins</Text>
          <Text style={[styles.statValue, { color: '#C084FC' }]}>{stats.staff_users}</Text>
          <Text style={styles.statSub}>is_staff = True</Text>
        </View>

        <View style={[styles.statTile, { borderColor: '#EAB30833' }]}>
          <Text style={styles.statLabel}>Verified</Text>
          <Text style={[styles.statValue, { color: '#FACC15' }]}>{stats.verified_users}</Text>
          <Text style={styles.statSub}>Email Confirmed</Text>
        </View>
      </ScrollView>

      {/* Filter Chips Bar */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterBar}>
        {[
          { key: 'all', label: 'All Users' },
          { key: 'active', label: 'Active' },
          { key: 'inactive', label: 'Inactive' },
          { key: 'google', label: 'Google' },
          { key: 'local', label: 'Local' },
          { key: 'staff', label: 'Staff' },
          { key: 'unverified', label: 'Unverified' },
        ].map((f) => {
          const isActive = activeFilter === f.key;
          return (
            <TouchableOpacity
              key={f.key}
              style={[styles.filterChip, isActive && styles.filterChipActive]}
              onPress={() => setActiveFilter(f.key as any)}
              activeOpacity={0.8}
            >
              <Text style={[styles.filterChipText, isActive && styles.filterChipTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );

  // Render User Card
  const renderUserItem = ({ item }: { item: AdminUserAccount }) => {
    const isCurrentUser = user?.id === item.id || user?.email === item.email;
    const initial = (item.name || item.username || item.email || 'U').charAt(0).toUpperCase();

    return (
      <View style={styles.userCard}>
        {/* Top Card Row */}
        <View style={styles.userCardHeader}>
          <View style={styles.avatarWrap}>
            {item.picture ? (
              <Image source={{ uri: item.picture }} style={styles.avatarImg} />
            ) : (
              <View style={[styles.avatarInitial, { backgroundColor: item.is_staff ? '#A855F722' : '#F43F5E22' }]}>
                <Text style={[styles.avatarText, { color: item.is_staff ? '#C084FC' : '#FB7185' }]}>{initial}</Text>
              </View>
            )}
            {item.is_active ? (
              <View style={styles.activeDot} />
            ) : (
              <View style={[styles.activeDot, { backgroundColor: '#EF4444' }]} />
            )}
          </View>

          <View style={styles.userCoreInfo}>
            <View style={styles.nameRow}>
              <Text style={styles.userFullName} numberOfLines={1}>
                {item.name || 'Unnamed User'}
              </Text>
              {isCurrentUser && (
                <View style={styles.youBadge}>
                  <Text style={styles.youBadgeText}>YOU</Text>
                </View>
              )}
            </View>

            <Text style={styles.userHandleText} numberOfLines={1}>
              @{item.username || 'no_handle'}
            </Text>

            <Text style={styles.userEmailText} numberOfLines={1}>
              {item.email}
            </Text>
          </View>
        </View>

        {/* Schema Status Badges */}
        <View style={styles.badgesRow}>
          {/* Auth Provider */}
          <View style={[styles.schemaBadge, item.auth_provider === 'google' ? styles.badgeGoogle : styles.badgeLocal]}>
            <Text style={[styles.badgeText, item.auth_provider === 'google' ? styles.badgeTextGoogle : styles.badgeTextLocal]}>
              {item.auth_provider === 'google' ? 'Google OAuth' : 'Local Auth'}
            </Text>
          </View>

          {/* Active status */}
          <View style={[styles.schemaBadge, item.is_active ? styles.badgeActive : styles.badgeInactive]}>
            <Text style={[styles.badgeText, item.is_active ? styles.badgeTextActive : styles.badgeTextInactive]}>
              {item.is_active ? 'Active' : 'Suspended'}
            </Text>
          </View>

          {/* Verified status */}
          <View style={[styles.schemaBadge, item.verified_email ? styles.badgeVerified : styles.badgeUnverified]}>
            <Text style={[styles.badgeText, item.verified_email ? styles.badgeTextVerified : styles.badgeTextUnverified]}>
              {item.verified_email ? 'Verified' : 'Unverified'}
            </Text>
          </View>

          {/* Staff */}
          {item.is_staff && (
            <View style={[styles.schemaBadge, styles.badgeStaff]}>
              <Text style={[styles.badgeText, styles.badgeTextStaff]}>
                {item.is_superuser ? 'Superuser' : 'Staff'}
              </Text>
            </View>
          )}
        </View>

        {/* Schema Fields Key-Value Rows */}
        <View style={styles.schemaFieldsBox}>
          <View style={styles.schemaFieldRow}>
            <Text style={styles.fieldKey}>UUID (id):</Text>
            <TouchableOpacity
              style={styles.fieldValRow}
              onPress={() => handleCopy(item.id, `id_${item.id}`)}
              activeOpacity={0.7}
            >
              <Text style={styles.fieldValMono} numberOfLines={1}>
                {item.id}
              </Text>
              <CopyIcon size={12} color={copiedKey === `id_${item.id}` ? '#10B981' : '#71717A'} />
            </TouchableOpacity>
          </View>

          <View style={styles.schemaFieldRow}>
            <Text style={styles.fieldKey}>Namespace:</Text>
            <TouchableOpacity
              style={styles.fieldValRow}
              onPress={() => handleCopy(item.namespace, `ns_${item.id}`)}
              activeOpacity={0.7}
            >
              <Text style={styles.fieldValMono} numberOfLines={1}>
                {item.namespace}
              </Text>
              <CopyIcon size={12} color={copiedKey === `ns_${item.id}` ? '#10B981' : '#71717A'} />
            </TouchableOpacity>
          </View>

          <View style={styles.schemaFieldRow}>
            <Text style={styles.fieldKey}>Created At:</Text>
            <Text style={styles.fieldValText}>
              {new Date(item.created_at).toLocaleDateString()} · {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </Text>
          </View>

          <View style={styles.schemaFieldRow}>
            <Text style={styles.fieldKey}>Personas Created:</Text>
            <Text style={[styles.fieldValText, { color: '#F43F5E', fontWeight: '700' }]}>
              {item.personas_count} personas
            </Text>
          </View>
        </View>

        {/* Card Actions */}
        <View style={styles.cardActionsRow}>
          <TouchableOpacity
            style={styles.actionBtnInspect}
            onPress={() => setInspectUser(item)}
            activeOpacity={0.8}
          >
            <Text style={styles.actionBtnInspectText}>Inspect Schema</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.actionBtnEdit}
            onPress={() => handleOpenEdit(item)}
            activeOpacity={0.8}
          >
            <Text style={styles.actionBtnEditText}>Edit</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtnToggle, item.is_active ? styles.actionBtnSuspend : styles.actionBtnActivate]}
            onPress={() => handleQuickToggleActive(item)}
            activeOpacity={0.8}
          >
            <Text style={[styles.actionBtnToggleText, item.is_active ? styles.textSuspend : styles.textActivate]}>
              {item.is_active ? 'Suspend' : 'Activate'}
            </Text>
          </TouchableOpacity>

          {!isCurrentUser && (
            <TouchableOpacity
              style={styles.actionBtnDelete}
              onPress={() => setUserToDelete(item)}
              activeOpacity={0.8}
            >
              <Text style={styles.actionBtnDeleteText}>Delete</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safeContainer} edges={['top', 'bottom']}>
      {/* Top Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <BackIcon size={20} color="#FFFFFF" />
        </TouchableOpacity>

        <View style={styles.headerTitleCol}>
          <View style={styles.titleWithShield}>
            <ShieldIcon size={18} color="#F43F5E" />
            <Text style={styles.headerTitle}>Admin Console</Text>
          </View>
          <Text style={styles.headerSubtitle}>Database Users & Schema Inspector</Text>
        </View>

        <View style={styles.headerActionsRight}>
          <TouchableOpacity
            style={styles.iconCircleBtn}
            onPress={() => loadUsers(true)}
            activeOpacity={0.7}
          >
            <RefreshIcon size={16} color="#FFFFFF" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.addUserButton}
            onPress={handleOpenCreate}
            activeOpacity={0.8}
          >
            <PlusIcon size={16} color="#FFFFFF" />
            <Text style={styles.addUserButtonText}>Add User</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Search Bar */}
      <View style={styles.searchBarWrapper}>
        <View style={styles.searchBarContainer}>
          <SearchIcon size={16} color="#71717A" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name, email, @handle, UUID, namespace..."
            placeholderTextColor="#71717A"
            value={searchQuery}
            onChangeText={setSearchQuery}
            returnKeyType="search"
            onSubmitEditing={() => loadUsers()}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <CloseIcon size={14} color="#71717A" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Users List */}
      {loading ? (
        <View style={styles.centerLoading}>
          <ActivityIndicator size="large" color="#F43F5E" />
          <Text style={styles.loadingText}>Fetching database schema & accounts...</Text>
        </View>
      ) : (
        <FlatList
          data={users}
          keyExtractor={(item) => item.id}
          renderItem={renderUserItem}
          ListHeaderComponent={renderStatsHeader}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => loadUsers(true)}
              tintColor="#F43F5E"
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <ShieldIcon size={36} color="#3F3F46" />
              <Text style={styles.emptyTitle}>No matching accounts</Text>
              <Text style={styles.emptySubtitle}>Try adjusting your search query or filter tags.</Text>
            </View>
          }
        />
      )}

      {/* ========================================================================= */}
      {/* MODAL 1: Inspect Schema Modal */}
      {/* ========================================================================= */}
      <Modal
        visible={!!inspectUser}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setInspectUser(null)}
      >
        <SafeAreaView style={styles.modalBackdrop} edges={['top', 'bottom']}>
          <View style={styles.modalHeader}>
            <View>
              <Text style={styles.modalTitle}>Schema Inspector</Text>
              <Text style={styles.modalSub}>{inspectUser?.email}</Text>
            </View>
            <TouchableOpacity
              style={styles.modalCloseCircle}
              onPress={() => setInspectUser(null)}
            >
              <CloseIcon size={18} color="#FFFFFF" />
            </TouchableOpacity>
          </View>

          {inspectUser && (
            <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
              <View style={styles.rawSchemaBox}>
                <Text style={styles.schemaSectionTitle}>POSTGRESQL COLUMNS (User Model)</Text>

                {[
                  { key: 'id', label: 'Primary Key (UUID)', val: inspectUser.id, copyable: true },
                  { key: 'namespace', label: 'Reeve Memory Partition', val: inspectUser.namespace, copyable: true },
                  { key: 'email', label: 'Email Address', val: inspectUser.email, copyable: true },
                  { key: 'username', label: 'Handle (@)', val: inspectUser.username ? `@${inspectUser.username}` : 'NULL' },
                  { key: 'name', label: 'Display Name', val: inspectUser.name || 'EMPTY' },
                  { key: 'given_name', label: 'Given Name', val: inspectUser.given_name || 'EMPTY' },
                  { key: 'family_name', label: 'Family Name', val: inspectUser.family_name || 'EMPTY' },
                  { key: 'auth_provider', label: 'Auth Provider', val: inspectUser.auth_provider },
                  { key: 'google_sub', label: 'Google Sub Claim', val: inspectUser.google_sub || 'N/A' },
                  { key: 'verified_email', label: 'Verified Status', val: inspectUser.verified_email ? 'TRUE' : 'FALSE' },
                  { key: 'is_active', label: 'Active Status', val: inspectUser.is_active ? 'TRUE' : 'FALSE' },
                  { key: 'is_staff', label: 'Staff Privileges', val: inspectUser.is_staff ? 'TRUE' : 'FALSE' },
                  { key: 'is_superuser', label: 'Superuser Privileges', val: inspectUser.is_superuser ? 'TRUE' : 'FALSE' },
                  { key: 'created_at', label: 'Created Timestamp', val: inspectUser.created_at },
                  { key: 'updated_at', label: 'Updated Timestamp', val: inspectUser.updated_at },
                  { key: 'last_login', label: 'Last Login', val: inspectUser.last_login || 'Never' },
                  { key: 'personas_count', label: 'Linked Personas', val: `${inspectUser.personas_count} personas` },
                  { key: 'picture', label: 'Avatar URL / Blob', val: inspectUser.picture ? `${inspectUser.picture.substring(0, 70)}...` : 'NONE' },
                ].map((row) => (
                  <View key={row.key} style={styles.inspectRow}>
                    <View style={styles.inspectKeyCol}>
                      <Text style={styles.inspectKeyText}>{row.key}</Text>
                      <Text style={styles.inspectTypeLabel}>{row.label}</Text>
                    </View>
                    <View style={styles.inspectValCol}>
                      <Text style={styles.inspectValText} selectable numberOfLines={3}>
                        {row.val}
                      </Text>
                      {row.copyable && (
                        <TouchableOpacity
                          style={styles.copyPill}
                          onPress={() => handleCopy(String(row.val), row.key)}
                        >
                          <Text style={styles.copyPillText}>
                            {copiedKey === row.key ? 'Copied' : 'Copy'}
                          </Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                ))}
              </View>

              {/* Raw JSON viewer */}
              <View style={styles.jsonDumpBox}>
                <View style={styles.jsonHeader}>
                  <Text style={styles.jsonTitle}>RAW JSON OBJECT</Text>
                  <TouchableOpacity
                    style={styles.copyJsonBtn}
                    onPress={() => handleCopy(JSON.stringify(inspectUser, null, 2), 'raw_json')}
                  >
                    <CopyIcon size={12} color="#FFFFFF" />
                    <Text style={styles.copyJsonBtnText}>
                      {copiedKey === 'raw_json' ? 'Copied!' : 'Copy JSON'}
                    </Text>
                  </TouchableOpacity>
                </View>
                <Text style={styles.jsonCode} selectable>
                  {JSON.stringify(inspectUser, null, 2)}
                </Text>
              </View>
            </ScrollView>
          )}
        </SafeAreaView>
      </Modal>

      {/* ========================================================================= */}
      {/* MODAL 2: Create / Edit User Modal */}
      {/* ========================================================================= */}
      <Modal
        visible={isCreateModalOpen || !!editUser}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => {
          setIsCreateModalOpen(false);
          setEditUser(null);
        }}
      >
        <SafeAreaView style={styles.modalBackdrop} edges={['top', 'bottom']}>
          <KeyboardAvoidingView
            style={{ flex: 1 }}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          >
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle}>
                  {editUser ? 'Edit User Account' : 'Create User Account'}
                </Text>
                <Text style={styles.modalSub}>
                  {editUser ? editUser.email : 'Insert row into PostgreSQL User table'}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.modalCloseCircle}
                onPress={() => {
                  setIsCreateModalOpen(false);
                  setEditUser(null);
                }}
              >
                <CloseIcon size={18} color="#FFFFFF" />
              </TouchableOpacity>
            </View>

            {formError && (
              <View style={styles.formErrorBanner}>
                <Text style={styles.formErrorText}>{formError}</Text>
              </View>
            )}

            <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
              {/* Email */}
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Email Address *</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="user@example.com"
                  placeholderTextColor="#52525B"
                  value={formData.email}
                  onChangeText={(v) => setFormData((p) => ({ ...p, email: v }))}
                  keyboardType="email-address"
                  autoCapitalize="none"
                />
              </View>

              {/* Username */}
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Username (@handle)</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="e.g. ankesh_dev"
                  placeholderTextColor="#52525B"
                  value={formData.username}
                  onChangeText={(v) => setFormData((p) => ({ ...p, username: v }))}
                  autoCapitalize="none"
                />
              </View>

              {/* Full Name */}
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Full Display Name</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="e.g. Ankesh Kumar"
                  placeholderTextColor="#52525B"
                  value={formData.name}
                  onChangeText={(v) => setFormData((p) => ({ ...p, name: v }))}
                />
              </View>

              {/* Given & Family Name */}
              <View style={styles.formRowTwo}>
                <View style={[styles.formGroup, { flex: 1 }]}>
                  <Text style={styles.formLabel}>Given Name</Text>
                  <TextInput
                    style={styles.formInput}
                    placeholder="Ankesh"
                    placeholderTextColor="#52525B"
                    value={formData.given_name}
                    onChangeText={(v) => setFormData((p) => ({ ...p, given_name: v }))}
                  />
                </View>
                <View style={[styles.formGroup, { flex: 1 }]}>
                  <Text style={styles.formLabel}>Family Name</Text>
                  <TextInput
                    style={styles.formInput}
                    placeholder="Kumar"
                    placeholderTextColor="#52525B"
                    value={formData.family_name}
                    onChangeText={(v) => setFormData((p) => ({ ...p, family_name: v }))}
                  />
                </View>
              </View>

              {/* Password */}
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>
                  {editUser ? 'Reset Password (leave empty to keep current)' : 'Password (for local login)'}
                </Text>
                <TextInput
                  style={styles.formInput}
                  placeholder={editUser ? '••••••••' : 'Minimum 6 characters'}
                  placeholderTextColor="#52525B"
                  value={formData.password}
                  onChangeText={(v) => setFormData((p) => ({ ...p, password: v }))}
                  secureTextEntry
                />
              </View>

              {/* Auth Provider */}
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Auth Provider</Text>
                <View style={styles.providerPickerRow}>
                  {['local', 'google'].map((prov) => (
                    <TouchableOpacity
                      key={prov}
                      style={[
                        styles.providerChoice,
                        formData.auth_provider === prov && styles.providerChoiceActive,
                      ]}
                      onPress={() => setFormData((p) => ({ ...p, auth_provider: prov }))}
                    >
                      <Text
                        style={[
                          styles.providerChoiceText,
                          formData.auth_provider === prov && styles.providerChoiceTextActive,
                        ]}
                      >
                        {prov === 'google' ? 'Google OAuth' : 'Local Password'}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Profile Picture URL */}
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Profile Picture URL</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="https://... or data:image/..."
                  placeholderTextColor="#52525B"
                  value={formData.picture}
                  onChangeText={(v) => setFormData((p) => ({ ...p, picture: v }))}
                  autoCapitalize="none"
                />
              </View>

              {/* Switches / Schema Boolean Flags */}
              <View style={styles.switchGroupSection}>
                <Text style={styles.switchSectionHeader}>SCHEMA PERMISSION FLAGS</Text>

                <View style={styles.switchItemRow}>
                  <View style={styles.switchTextCol}>
                    <Text style={styles.switchLabel}>is_active</Text>
                    <Text style={styles.switchSub}>Account allowed to sign in and chat</Text>
                  </View>
                  <Switch
                    value={formData.is_active}
                    onValueChange={(val) => setFormData((p) => ({ ...p, is_active: val }))}
                    trackColor={{ false: '#3F3F46', true: '#10B981' }}
                    thumbColor="#FFFFFF"
                  />
                </View>

                <View style={styles.switchItemRow}>
                  <View style={styles.switchTextCol}>
                    <Text style={styles.switchLabel}>verified_email</Text>
                    <Text style={styles.switchSub}>Email confirmed via OTP / Google verification</Text>
                  </View>
                  <Switch
                    value={formData.verified_email}
                    onValueChange={(val) => setFormData((p) => ({ ...p, verified_email: val }))}
                    trackColor={{ false: '#3F3F46', true: '#3B82F6' }}
                    thumbColor="#FFFFFF"
                  />
                </View>

                <View style={styles.switchItemRow}>
                  <View style={styles.switchTextCol}>
                    <Text style={styles.switchLabel}>is_staff</Text>
                    <Text style={styles.switchSub}>Grants admin console access & privileges</Text>
                  </View>
                  <Switch
                    value={formData.is_staff}
                    onValueChange={(val) => setFormData((p) => ({ ...p, is_staff: val }))}
                    trackColor={{ false: '#3F3F46', true: '#A855F7' }}
                    thumbColor="#FFFFFF"
                  />
                </View>

                <View style={styles.switchItemRow}>
                  <View style={styles.switchTextCol}>
                    <Text style={styles.switchLabel}>is_superuser</Text>
                    <Text style={styles.switchSub}>Full superuser bypass on all models</Text>
                  </View>
                  <Switch
                    value={formData.is_superuser}
                    onValueChange={(val) => setFormData((p) => ({ ...p, is_superuser: val }))}
                    trackColor={{ false: '#3F3F46', true: '#F43F5E' }}
                    thumbColor="#FFFFFF"
                  />
                </View>
              </View>

              {/* Submit Buttons */}
              <View style={styles.modalSubmitBar}>
                <TouchableOpacity
                  style={styles.cancelButton}
                  onPress={() => {
                    setIsCreateModalOpen(false);
                    setEditUser(null);
                  }}
                  disabled={formSaving}
                >
                  <Text style={styles.cancelButtonText}>Cancel</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.saveButton}
                  onPress={editUser ? handleSaveEdit : handleSaveCreate}
                  disabled={formSaving}
                >
                  {formSaving ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <Text style={styles.saveButtonText}>
                      {editUser ? 'Save Changes' : 'Create User'}
                    </Text>
                  )}
                </TouchableOpacity>
              </View>
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>

      {/* ========================================================================= */}
      {/* MODAL 3: Delete Confirmation Modal */}
      {/* ========================================================================= */}
      <Modal
        visible={!!userToDelete}
        transparent
        animationType="fade"
        onRequestClose={() => setUserToDelete(null)}
      >
        <View style={styles.confirmBackdrop}>
          <View style={styles.confirmBox}>
            <View style={styles.confirmIconWrap}>
              <Text style={{ fontSize: 24 }}>⚠️</Text>
            </View>
            <Text style={styles.confirmTitle}>Delete User Account?</Text>
            <Text style={styles.confirmMsg}>
              Are you sure you want to permanently delete{' '}
              <Text style={{ color: '#F43F5E', fontWeight: '700' }}>
                {userToDelete?.email}
              </Text>
              ? This action cannot be undone and will delete their DB row and associated memory partitions.
            </Text>

            <View style={styles.confirmBtnsRow}>
              <TouchableOpacity
                style={styles.confirmCancelBtn}
                onPress={() => setUserToDelete(null)}
              >
                <Text style={styles.confirmCancelText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.confirmDeleteBtn}
                onPress={handleConfirmDelete}
              >
                <Text style={styles.confirmDeleteText}>Delete Account</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeContainer: {
    flex: 1,
    backgroundColor: '#060609',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#161622',
    backgroundColor: '#09090E',
  },
  backButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#161622',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  headerTitleCol: {
    flex: 1,
  },
  titleWithShield: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  headerSubtitle: {
    color: '#71717A',
    fontSize: 11,
    fontWeight: '500',
    marginTop: 2,
  },
  headerActionsRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  iconCircleBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#181822',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#27273A',
  },
  addUserButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#F43F5E',
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
  },
  addUserButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },

  // Search
  searchBarWrapper: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 6,
    backgroundColor: '#09090E',
  },
  searchBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#13131C',
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 42,
    borderWidth: 1,
    borderColor: '#222232',
    gap: 8,
  },
  searchInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 13,
  },

  // Stats
  statsContainer: {
    paddingTop: 10,
    paddingBottom: 6,
  },
  statsScroll: {
    paddingHorizontal: 16,
    gap: 10,
    paddingBottom: 10,
  },
  statTile: {
    backgroundColor: '#0F0F17',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderWidth: 1,
    minWidth: 105,
  },
  statLabel: {
    color: '#A1A1AA',
    fontSize: 11,
    fontWeight: '500',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '800',
    marginTop: 2,
  },
  statSub: {
    color: '#52525B',
    fontSize: 9,
    marginTop: 2,
  },

  // Filter Chips
  filterBar: {
    paddingHorizontal: 16,
    gap: 8,
    paddingVertical: 4,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#14141E',
    borderWidth: 1,
    borderColor: '#232334',
  },
  filterChipActive: {
    backgroundColor: '#F43F5E22',
    borderColor: '#F43F5E',
  },
  filterChipText: {
    color: '#A1A1AA',
    fontSize: 12,
    fontWeight: '600',
  },
  filterChipTextActive: {
    color: '#F43F5E',
  },

  // List
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 40,
    paddingTop: 6,
  },
  centerLoading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    color: '#A1A1AA',
    fontSize: 13,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
    gap: 10,
  },
  emptyTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  emptySubtitle: {
    color: '#71717A',
    fontSize: 13,
    textAlign: 'center',
    paddingHorizontal: 30,
  },

  // User Card
  userCard: {
    backgroundColor: '#0F0F17',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1D1D2C',
    padding: 14,
    marginBottom: 12,
  },
  userCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatarWrap: {
    position: 'relative',
  },
  avatarImg: {
    width: 48,
    height: 48,
    borderRadius: 24,
  },
  avatarInitial: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 18,
    fontWeight: '700',
  },
  activeDot: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#10B981',
    borderWidth: 2,
    borderColor: '#0F0F17',
  },
  userCoreInfo: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  userFullName: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
    flexShrink: 1,
  },
  youBadge: {
    backgroundColor: '#F43F5E22',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#F43F5E55',
  },
  youBadgeText: {
    color: '#F43F5E',
    fontSize: 9,
    fontWeight: '800',
  },
  userHandleText: {
    color: '#A1A1AA',
    fontSize: 12,
    fontWeight: '500',
    marginTop: 1,
  },
  userEmailText: {
    color: '#71717A',
    fontSize: 12,
    marginTop: 2,
  },

  // Badges
  badgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 12,
  },
  schemaBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  badgeGoogle: { backgroundColor: '#3B82F618' },
  badgeTextGoogle: { color: '#60A5FA' },
  badgeLocal: { backgroundColor: '#71717A18' },
  badgeTextLocal: { color: '#A1A1AA' },
  badgeActive: { backgroundColor: '#10B98118' },
  badgeTextActive: { color: '#34D399' },
  badgeInactive: { backgroundColor: '#EF444418' },
  badgeTextInactive: { color: '#F87171' },
  badgeVerified: { backgroundColor: '#14B8A618' },
  badgeTextVerified: { color: '#2DD4BF' },
  badgeUnverified: { backgroundColor: '#F59E0B18' },
  badgeTextUnverified: { color: '#FBBF24' },
  badgeStaff: { backgroundColor: '#A855F718' },
  badgeTextStaff: { color: '#C084FC' },

  // Schema box
  schemaFieldsBox: {
    backgroundColor: '#09090F',
    borderRadius: 8,
    padding: 10,
    marginTop: 12,
    gap: 6,
    borderWidth: 1,
    borderColor: '#191924',
  },
  schemaFieldRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  fieldKey: {
    color: '#71717A',
    fontSize: 11,
    fontWeight: '500',
  },
  fieldValRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    maxWidth: '65%',
  },
  fieldValMono: {
    color: '#D4D4D8',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  fieldValText: {
    color: '#D4D4D8',
    fontSize: 11,
  },

  // Actions
  cardActionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#171723',
  },
  actionBtnInspect: {
    flex: 1,
    backgroundColor: '#181824',
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#28283C',
  },
  actionBtnInspectText: {
    color: '#E4E4E7',
    fontSize: 11,
    fontWeight: '600',
  },
  actionBtnEdit: {
    backgroundColor: '#1E1E2E',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#32324A',
  },
  actionBtnEditText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  actionBtnToggle: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: 'center',
  },
  actionBtnSuspend: {
    backgroundColor: '#EF444415',
  },
  actionBtnActivate: {
    backgroundColor: '#10B98115',
  },
  actionBtnToggleText: {
    fontSize: 11,
    fontWeight: '600',
  },
  textSuspend: { color: '#F87171' },
  textActivate: { color: '#34D399' },
  actionBtnDelete: {
    backgroundColor: '#EF444420',
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
  },
  actionBtnDeleteText: {
    color: '#F87171',
    fontSize: 11,
    fontWeight: '600',
  },

  // Modal Common
  modalBackdrop: {
    flex: 1,
    backgroundColor: '#09090F',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1A1A28',
  },
  modalTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
  modalSub: {
    color: '#71717A',
    fontSize: 12,
    marginTop: 2,
  },
  modalCloseCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1A1A26',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBody: {
    flex: 1,
    paddingHorizontal: 18,
    paddingTop: 14,
  },

  // Inspect Modal
  rawSchemaBox: {
    backgroundColor: '#11111B',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#202032',
    gap: 12,
  },
  schemaSectionTitle: {
    color: '#F43F5E',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  inspectRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#181824',
    gap: 10,
  },
  inspectKeyCol: {
    width: '42%',
  },
  inspectKeyText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  inspectTypeLabel: {
    color: '#71717A',
    fontSize: 10,
    marginTop: 2,
  },
  inspectValCol: {
    flex: 1,
    alignItems: 'flex-end',
    gap: 4,
  },
  inspectValText: {
    color: '#D4D4D8',
    fontSize: 12,
    textAlign: 'right',
  },
  copyPill: {
    backgroundColor: '#1E1E2C',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  copyPillText: {
    color: '#A1A1AA',
    fontSize: 10,
    fontWeight: '600',
  },

  // JSON Dump
  jsonDumpBox: {
    backgroundColor: '#0B0B12',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1C1C2C',
    marginTop: 16,
    marginBottom: 40,
  },
  jsonHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  jsonTitle: {
    color: '#71717A',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  copyJsonBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#1E1E2E',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  copyJsonBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  jsonCode: {
    color: '#34D399',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    lineHeight: 16,
  },

  // Form Styles
  formGroup: {
    marginBottom: 14,
  },
  formLabel: {
    color: '#D4D4D8',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 6,
  },
  formInput: {
    backgroundColor: '#14141E',
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
    color: '#FFFFFF',
    fontSize: 13,
    borderWidth: 1,
    borderColor: '#242436',
  },
  formRowTwo: {
    flexDirection: 'row',
    gap: 12,
  },
  providerPickerRow: {
    flexDirection: 'row',
    gap: 10,
  },
  providerChoice: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#14141E',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#242436',
  },
  providerChoiceActive: {
    backgroundColor: '#F43F5E22',
    borderColor: '#F43F5E',
  },
  providerChoiceText: {
    color: '#A1A1AA',
    fontSize: 12,
    fontWeight: '600',
  },
  providerChoiceTextActive: {
    color: '#F43F5E',
  },
  switchGroupSection: {
    backgroundColor: '#12121C',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#222234',
    marginTop: 6,
    marginBottom: 20,
    gap: 14,
  },
  switchSectionHeader: {
    color: '#F43F5E',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  switchItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  switchTextCol: {
    flex: 1,
    paddingRight: 12,
  },
  switchLabel: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  switchSub: {
    color: '#71717A',
    fontSize: 11,
    marginTop: 2,
  },
  formErrorBanner: {
    backgroundColor: '#EF444422',
    padding: 10,
    marginHorizontal: 18,
    marginTop: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#EF444444',
  },
  formErrorText: {
    color: '#F87171',
    fontSize: 12,
    fontWeight: '500',
  },
  modalSubmitBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingBottom: 40,
    marginTop: 10,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#1E1E2C',
    alignItems: 'center',
  },
  cancelButtonText: {
    color: '#A1A1AA',
    fontSize: 14,
    fontWeight: '600',
  },
  saveButton: {
    flex: 2,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#F43F5E',
    alignItems: 'center',
  },
  saveButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },

  // Confirm Modal
  confirmBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  confirmBox: {
    width: '100%',
    backgroundColor: '#12121A',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#262638',
    alignItems: 'center',
  },
  confirmIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#EF444420',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  confirmTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
  confirmMsg: {
    color: '#A1A1AA',
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 18,
    marginTop: 8,
    marginBottom: 20,
  },
  confirmBtnsRow: {
    flexDirection: 'row',
    gap: 10,
    width: '100%',
  },
  confirmCancelBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#1E1E2C',
    alignItems: 'center',
  },
  confirmCancelText: {
    color: '#D4D4D8',
    fontSize: 13,
    fontWeight: '600',
  },
  confirmDeleteBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#EF4444',
    alignItems: 'center',
  },
  confirmDeleteText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
  },
});
