"""Exercise single-snapshot publication using isolated local Git remotes."""

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "commit-timestamp.sh"
ENV=dict(os.environ,GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null')
for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR','GIT_AUTHOR_NAME','GIT_AUTHOR_EMAIL','GIT_AUTHOR_DATE','GIT_COMMITTER_NAME','GIT_COMMITTER_EMAIL','GIT_COMMITTER_DATE'):
    ENV.pop(key,None)

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='site-snapshot-test-')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.repo=self.root/'site'
        self.remote=self.root/'remote.git'
        self.call(['git','init','--bare','--initial-branch=main',str(self.remote)],self.root)
        self.call(['git','init','--initial-branch=main',str(self.repo)],self.root)
        self.git('config','user.name','Site Publisher')
        self.git('config','user.email','publisher@example.test')
        shutil.copy2(SOURCE,self.repo/'commit-timestamp.sh')
        (self.repo/'obsolete.txt').write_text('obsolete')
        for value in ('one','two','three'):
            (self.repo/'current.txt').write_text(value)
            self.git('add','--all')
            self.git('commit','-m',value)
        self.git('remote','add','origin',str(self.remote))
        self.git('push','--set-upstream','origin','main')
        self.before=self.git('rev-parse','HEAD')
    def call(self,command,cwd=None,ok=True):
        result=subprocess.run(command,cwd=cwd or self.repo,env=ENV,text=True,capture_output=True)
        if ok and result.returncode:
            self.fail(f'{command}: {result.returncode}\n{result.stdout}\n{result.stderr}')
        return result
    def git(self,*args):
        return self.call(['git',*args]).stdout.strip()
    def remote_git(self,*args):
        return self.call(['git','--git-dir='+str(self.remote),*args]).stdout.strip()
    def run_script(self,*args,ok=True):
        return self.call([str(self.repo/'commit-timestamp.sh'),*args],self.root,ok)
    def test_parentless_signed_off_snapshot_stages_changes_and_pushes(self):
        (self.repo/'obsolete.txt').unlink()
        (self.repo/'.hidden').write_text('include hidden')
        (self.repo/'new').mkdir()
        (self.repo/'new'/'data.txt').write_text('new data')
        self.run_script()
        self.assertEqual(self.git('rev-list','--count','HEAD'),'1')
        self.assertEqual(self.remote_git('rev-list','--count','refs/heads/main'),'1')
        self.assertEqual(self.git('rev-parse','HEAD'),self.remote_git('rev-parse','refs/heads/main'))
        self.assertEqual(self.git('status','--porcelain'),'')
        message=self.git('log','-1','--format=%B')
        self.assertRegex(message,r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\n\nSigned-off-by: Site Publisher <publisher@example.test>$')
        self.assertEqual(set(self.git('ls-tree','-r','--name-only','HEAD').splitlines()),{'commit-timestamp.sh','current.txt','.hidden','new/data.txt'})
        self.assertEqual(self.git('rev-parse','origin/main'),self.git('rev-parse','HEAD'))
        # Recovery history remains in reflogs; it is not a parent of the new tip.
        self.assertIn(self.before,self.git('reflog','show','--format=%H','main'))
        (self.repo/'current.txt').write_text('four')
        self.run_script()
        self.assertEqual(self.git('rev-list','--count','HEAD'),'1')
        self.assertEqual(self.remote_git('rev-list','--count','refs/heads/main'),'1')
        self.assertEqual(self.remote_git('show','main:current.txt'),'four')
    def test_no_push_does_not_contact_bad_remote(self):
        self.git('remote','set-url','origin',str(self.root/'missing.git'))
        (self.repo/'current.txt').write_text('local only')
        self.run_script('--no-push')
        self.assertEqual(self.git('rev-list','--count','HEAD'),'1')
        self.assertEqual(self.remote_git('rev-parse','main'),self.before)
        self.assertEqual(self.git('status','--porcelain'),'')
    def test_remote_preflight_failure_preserves_head_and_index(self):
        self.git('remote','set-url','origin',str(self.root/'missing.git'))
        (self.repo/'current.txt').write_text('not staged')
        before_index=self.git('write-tree')
        result=self.run_script(ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        self.assertEqual(self.git('write-tree'),before_index)
    def test_detached_head_is_rejected(self):
        self.git('checkout','--detach')
        result=self.run_script('--no-push',ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
    def test_remote_race_cannot_be_overwritten(self):
        tree=self.remote_git('rev-parse','main^{tree}')
        command=['git','--git-dir='+str(self.remote),'-c','user.name=Concurrent Publisher','-c','user.email=concurrent@example.test','commit-tree',tree,'-p',self.before,'-m','concurrent update']
        contender=self.call(command).stdout.strip()
        hook=self.repo/'.git/hooks/pre-push'
        command=['git','--git-dir='+str(self.remote),'update-ref','refs/heads/main',contender,self.before]
        hook.write_text('#!/bin/sh\n'+shlex.join(command)+'\n')
        hook.chmod(0o755)
        (self.repo/'current.txt').write_text('conflicting publication')
        result=self.run_script(ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.remote_git('rev-parse','main'),contender)
        self.assertEqual(self.git('rev-list','--count','HEAD'),'1')
        self.assertIn('snapshot remains local',result.stderr)
    def test_uses_configured_remote_branch_only(self):
        self.git('push','origin','HEAD:refs/heads/pages')
        self.git('config','branch.main.merge','refs/heads/pages')
        (self.repo/'current.txt').write_text('publish pages')
        self.run_script()
        self.assertEqual(self.remote_git('rev-parse','pages'),self.git('rev-parse','HEAD'))
        self.assertEqual(self.remote_git('rev-parse','main'),self.before)
        self.assertEqual(self.remote_git('rev-list','--count','pages'),'1')
    def test_multiple_push_destinations_are_rejected_before_staging(self):
        self.git('remote','set-url','--add','--push','origin',str(self.remote))
        self.git('remote','set-url','--add','--push','origin',str(self.root/'another.git'))
        (self.repo/'current.txt').write_text('unstaged')
        before_index=self.git('write-tree')
        result=self.run_script(ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        self.assertEqual(self.git('write-tree'),before_index)
    def test_missing_remote_branch_can_be_created(self):
        self.git('config','branch.main.merge','refs/heads/new-pages')
        self.run_script()
        self.assertEqual(self.remote_git('rev-parse','new-pages'),self.git('rev-parse','HEAD'))
        self.assertEqual(self.remote_git('rev-list','--count','new-pages'),'1')

if __name__=='__main__': unittest.main(verbosity=2)
