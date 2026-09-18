'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import { adminApi, PermissionItem, RoleItem } from '@/lib/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function AdminPermissionsPage() {
  const { data: permissions = [], mutate: mutatePerms, isLoading: loadingPerms } = useSWR(
    'admin-permissions',
    adminApi.listPermissions
  );
  const { data: roles = [], mutate: mutateRoles, isLoading: loadingRoles } = useSWR(
    'admin-roles',
    adminApi.listRoles
  );

  const [savingRoleId, setSavingRoleId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newSlug, setNewSlug] = useState<string>('');
  const [newName, setNewName] = useState<string>('');
  const [newDesc, setNewDesc] = useState<string>('');
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Filter permissions based on search term
  const filteredPermissions = permissions.filter(
    p =>
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Group permissions by category
  const categories = Array.from(new Set(filteredPermissions.map(p => p.category)));

  async function handleTogglePermission(role: RoleItem, permCode: string) {
    const isAssigned = role.permissions.includes(permCode);
    const updatedPermissions = isAssigned
      ? role.permissions.filter(c => c !== permCode)
      : [...role.permissions, permCode];

    await saveRolePermissions(role.id, updatedPermissions);
  }

  async function handleBulkRoleToggle(role: RoleItem, enableAll: boolean) {
    const allCodes = permissions.map(p => p.code);
    const updatedPermissions = enableAll ? Array.from(new Set([...role.permissions, ...allCodes])) : [];
    await saveRolePermissions(role.id, updatedPermissions);
  }

  async function handleBulkCategoryToggle(role: RoleItem, category: string, enable: boolean) {
    const categoryCodes = permissions.filter(p => p.category === category).map(p => p.code);
    let updatedPermissions: string[];
    if (enable) {
      updatedPermissions = Array.from(new Set([...role.permissions, ...categoryCodes]));
    } else {
      updatedPermissions = role.permissions.filter(c => !categoryCodes.includes(c));
    }
    await saveRolePermissions(role.id, updatedPermissions);
  }

  async function saveRolePermissions(roleId: string, updatedPermissions: string[]) {
    setSavingRoleId(roleId);
    try {
      await adminApi.updateRoleMatrix(roleId, updatedPermissions);
      await mutateRoles();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update matrix');
    } finally {
      setSavingRoleId(null);
    }
  }

  async function handleCreateRole(e: React.FormEvent) {
    e.preventDefault();
    if (!newSlug || !newName) return;

    setCreateLoading(true);
    setErrorMsg('');
    try {
      await adminApi.createRole({
        slug: newSlug.toLowerCase().trim().replace(/\s+/g, '_'),
        name: newName.trim(),
        description: newDesc.trim(),
        permissions: [],
      });
      await mutateRoles();
      setShowCreateModal(false);
      setNewSlug('');
      setNewName('');
      setNewDesc('');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleDeleteRole(roleId: string, roleName: string) {
    if (!confirm(`Are you sure you want to delete custom role "${roleName}"?`)) return;
    try {
      await adminApi.deleteRole(roleId);
      await mutateRoles();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete role');
    }
  }

  if (loadingPerms || loadingRoles) {
    return <PageLoader />;
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Dynamic Role & Permission Matrix</h1>
          <p className={styles.subtitle}>
            Granular itemized permission control. Assign specific feature actions across system & custom roles live.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <Input
            placeholder="🔍 Search permissions..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{ width: '220px', marginBottom: 0 }}
          />
          <Button onClick={() => setShowCreateModal(true)}>+ Create Custom Role</Button>
        </div>
      </header>

      <Card className={styles.matrixCard}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th style={{ width: '340px' }}>
                Permission / Feature ({permissions.length} total)
              </th>
              {roles.map(r => (
                <th key={r.id} className={styles.roleHeaderCell}>
                  <div className={styles.roleTitle}>
                    <span>{r.name}</span>
                    {r.is_system ? (
                      <Badge variant="info" style={{ fontSize: '9px', padding: '1px 4px' }}>
                        System
                      </Badge>
                    ) : (
                      <button
                        onClick={() => handleDeleteRole(r.id, r.name)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', fontSize: '11px' }}
                        title="Delete Role"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  <div className={styles.roleSlug}>{r.slug}</div>
                  <div style={{ display: 'flex', gap: '4px', justifyContent: 'center', marginTop: '6px' }}>
                    <button
                      type="button"
                      onClick={() => handleBulkRoleToggle(r, true)}
                      style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(59,130,246,0.15)', color: 'var(--color-accent)', border: 'none', cursor: 'pointer' }}
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      onClick={() => handleBulkRoleToggle(r, false)}
                      style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(239,68,68,0.15)', color: 'var(--color-danger)', border: 'none', cursor: 'pointer' }}
                    >
                      Clear All
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map(category => {
              const categoryPerms = filteredPermissions.filter(p => p.category === category);
              return (
                <React.Fragment key={category}>
                  <tr className={styles.categoryRow}>
                    <td className={styles.categoryTitle}>
                      📂 {category} ({categoryPerms.length})
                    </td>
                    {roles.map(r => {
                      const categoryCodes = categoryPerms.map(cp => cp.code);
                      const allChecked = categoryCodes.every(code => r.permissions.includes(code));
                      return (
                        <td key={r.id} style={{ textAlign: 'center', background: 'rgba(99,102,241,0.04)' }}>
                          <button
                            type="button"
                            onClick={() => handleBulkCategoryToggle(r, category, !allChecked)}
                            style={{
                              fontSize: '10px', padding: '2px 8px', borderRadius: '4px',
                              border: '1px solid var(--color-border)', cursor: 'pointer',
                              background: allChecked ? 'rgba(16,185,129,0.15)' : 'var(--color-surface-2)',
                              color: allChecked ? '#10B981' : 'var(--color-text-2)',
                              fontWeight: 600
                            }}
                          >
                            {allChecked ? '✓ All' : 'Toggle Category'}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                  {categoryPerms.map(perm => (
                    <tr key={perm.code}>
                      <td>
                        <div className={styles.permName}>{perm.name}</div>
                        <span className={styles.permCode}>{perm.code}</span>
                        <div className={styles.permDesc}>{perm.description}</div>
                      </td>
                      {roles.map(role => {
                        const checked = role.permissions.includes(perm.code);
                        const disabled = savingRoleId === role.id;

                        return (
                          <td key={role.id} className={styles.cellCenter}>
                            <input
                              type="checkbox"
                              className={styles.checkbox}
                              checked={checked}
                              disabled={disabled}
                              onChange={() => handleTogglePermission(role, perm.code)}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </Card>

      {showCreateModal && (
        <div className={styles.modalOverlay} onClick={() => setShowCreateModal(false)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>Create Custom Role</h3>
            <form onSubmit={handleCreateRole} className={styles.form}>
              <Input
                label="Role Name"
                value={newName}
                onChange={e => {
                  setNewName(e.target.value);
                  if (!newSlug) setNewSlug(e.target.value.toLowerCase().replace(/\s+/g, '_'));
                }}
                placeholder="e.g. Store Auditor"
                required
              />
              <Input
                label="Role Slug"
                value={newSlug}
                onChange={e => setNewSlug(e.target.value)}
                placeholder="e.g. store_auditor"
                required
              />
              <Input
                label="Description"
                value={newDesc}
                onChange={e => setNewDesc(e.target.value)}
                placeholder="Brief summary of role responsibilities"
              />

              {errorMsg && <p style={{ color: 'var(--color-danger)', fontSize: '13px' }}>{errorMsg}</p>}

              <div className={styles.actions}>
                <Button type="button" variant="secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" loading={createLoading}>
                  Save Role
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
