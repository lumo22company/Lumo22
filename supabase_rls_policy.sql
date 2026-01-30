-- Enable Row Level Security and create policy for leads table
-- Run this in Supabase SQL Editor after creating the table

-- Enable RLS on the leads table
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows anyone to insert leads (for public form submissions)
CREATE POLICY "Allow public inserts on leads"
ON leads
FOR INSERT
TO anon, authenticated
WITH CHECK (true);

-- Create a policy that allows reading leads (you might want to restrict this later)
CREATE POLICY "Allow public reads on leads"
ON leads
FOR SELECT
TO anon, authenticated
USING (true);

-- Create a policy that allows updates (for status changes, etc.)
CREATE POLICY "Allow public updates on leads"
ON leads
FOR UPDATE
TO anon, authenticated
USING (true);
