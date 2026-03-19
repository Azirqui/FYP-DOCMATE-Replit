-- Code Documentation AI - Database Migration
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

-- 1. Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);

-- 2. Project files table
CREATE TABLE IF NOT EXISTS project_files (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_project_files_project_id ON project_files(project_id);

-- 3. Generated documentation table
CREATE TABLE IF NOT EXISTS generated_docs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL CHECK (doc_type IN ('overview', 'module', 'docstring')),
    module_name TEXT,
    content TEXT NOT NULL DEFAULT '',
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_generated_docs_project_id ON generated_docs(project_id);

-- 4. Generated UML diagrams table
CREATE TABLE IF NOT EXISTS generated_uml (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    diagram_type TEXT NOT NULL CHECK (diagram_type IN ('class', 'dependency', 'inheritance')),
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_generated_uml_project_id ON generated_uml(project_id);

-- 5. Enable Row Level Security on all tables
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_uml ENABLE ROW LEVEL SECURITY;

-- 6. RLS Policies - users can only access their own data
-- Projects: user can CRUD their own projects
CREATE POLICY "Users can view own projects"
    ON projects FOR SELECT
    USING (auth.uid()::text = user_id);

CREATE POLICY "Users can create own projects"
    ON projects FOR INSERT
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users can update own projects"
    ON projects FOR UPDATE
    USING (auth.uid()::text = user_id);

CREATE POLICY "Users can delete own projects"
    ON projects FOR DELETE
    USING (auth.uid()::text = user_id);

-- Project files: accessible if user owns the parent project
CREATE POLICY "Users can view own project files"
    ON project_files FOR SELECT
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can create own project files"
    ON project_files FOR INSERT
    WITH CHECK (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can delete own project files"
    ON project_files FOR DELETE
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

-- Generated docs: accessible if user owns the parent project
CREATE POLICY "Users can view own generated docs"
    ON generated_docs FOR SELECT
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can create own generated docs"
    ON generated_docs FOR INSERT
    WITH CHECK (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can update own generated docs"
    ON generated_docs FOR UPDATE
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can delete own generated docs"
    ON generated_docs FOR DELETE
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

-- Generated UML: accessible if user owns the parent project
CREATE POLICY "Users can view own generated uml"
    ON generated_uml FOR SELECT
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can create own generated uml"
    ON generated_uml FOR INSERT
    WITH CHECK (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

CREATE POLICY "Users can delete own generated uml"
    ON generated_uml FOR DELETE
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text));

-- 7. Service role bypass (for backend using SUPABASE_SERVICE_KEY)
-- The service role key automatically bypasses RLS, so the backend
-- can access all data when using the service key.

-- 8. Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_generated_docs_updated_at
    BEFORE UPDATE ON generated_docs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
